# Emisor por servidor: TUQUITO_ISSUER_SERVICE_URL en el entorno o en .env junto al .exe (ver client_env).
##################################################
###              Imports externos              ###
##################################################

from base64 import b64decode, b64encode
import os
import re
import sys
from requests import get, post, exceptions as requests_exceptions # Explicit import for requests exceptions
import threading
import PyKCS11
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
from cryptography.hazmat.primitives import hashes, serialization
from flask import jsonify

from client_env import load_client_dotenv

load_client_dotenv()

##################################################
###          Custom Exceptions                 ###
##################################################

class CertificateError(Exception):
    """Base class for certificate related errors."""
    def __init__(self, message, status_code=500):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class AIAExtensionNotFoundError(CertificateError):
    """Error when AIA extension or CA_ISSUERS descriptor is not found."""
    def __init__(self, message="No se encontró la extensión AIA o el descriptor CA_ISSUERS."):
        super().__init__(message, 404)

class IssuerCertificateFetchError(CertificateError):
    """Error when fetching an issuer certificate from a URL."""
    def __init__(self, message="Error al obtener el certificado del emisor.", original_exception=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message, 500)

class CertificateParsingError(CertificateError):
    """Error when parsing certificate data (DER/PEM)."""
    def __init__(self, message="Error al parsear el certificado.", original_exception=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message, 500)

class PKCS11LoadError(CertificateError):
    """Error when loading the PKCS#11 library."""
    def __init__(self, message="Error al cargar la biblioteca PKCS#11.", original_exception=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message, 500)

class TokenNotFoundError(CertificateError):
    """Error when no PKCS#11 tokens are found."""
    def __init__(self, message="No se encontraron tokens."):
        super().__init__(message, 404)

class TokenLoginError(CertificateError):
    """Error during token session opening or login."""
    def __init__(self, message="Error al abrir sesión o iniciar sesión en el token.", original_exception=None, error_type=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message, 500)
        self.error_type = error_type # e.g., "BAD_PIN"

##################################################
###          Certificate Functions             ###
##################################################

# Caché de certificados emisor (superiores) por token (p. ej. ATR hex) y huella del certificado inferior.
_issuer_cert_cache: dict[tuple[str, str], bytes] = {}
_issuer_cert_cache_lock = threading.Lock()


def _client_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _issuer_disk_cache_dir() -> str:
    d = os.path.join(_client_base_dir(), "issuer_cache")
    try:
        os.makedirs(d, exist_ok=True)
    except OSError:
        pass
    return d


def _issuer_disk_cache_path(token_key: str, lower_fp_hex: str) -> str:
    safe_tok = re.sub(r"[^A-Za-z0-9_-]+", "_", token_key)
    return os.path.join(_issuer_disk_cache_dir(), f"{safe_tok}_{lower_fp_hex}.der")


def _lower_cert_fingerprint_hex(cert: x509.Certificate) -> str:
    return cert.fingerprint(hashes.SHA256()).hex().upper()


def _store_issuer_cache(token_key: str | None, lower_cert: x509.Certificate, issuer_der: bytes) -> None:
    if not token_key:
        return
    cache_key = (token_key, _lower_cert_fingerprint_hex(lower_cert))
    with _issuer_cert_cache_lock:
        _issuer_cert_cache[cache_key] = issuer_der
    path = _issuer_disk_cache_path(token_key, cache_key[1])
    try:
        with open(path, "wb") as f:
            f.write(issuer_der)
    except OSError as e_w:
        print(f"No se pudo escribir caché de emisor en disco: {e_w}")


def _load_issuer_from_cache(token_key: str | None, lower_cert: x509.Certificate) -> x509.Certificate | None:
    if not token_key:
        return None
    fp = _lower_cert_fingerprint_hex(lower_cert)
    cache_key = (token_key, fp)
    with _issuer_cert_cache_lock:
        cached_der = _issuer_cert_cache.get(cache_key)
    if cached_der:
        try:
            print("Usando certificado emisor en caché en memoria (respaldo tras fallo de red o AIA).")
            c_mem = x509.load_der_x509_certificate(cached_der)
            if not _issuer_dn_matches_parent_candidate(lower_cert, c_mem):
                print("Caché en memoria no coincide con el emisor esperado; se elimina.")
                with _issuer_cert_cache_lock:
                    _issuer_cert_cache.pop(cache_key, None)
                return None
            return c_mem
        except ValueError as e_parse:
            print(f"Entrada de caché en memoria inválida, se elimina: {e_parse}")
            with _issuer_cert_cache_lock:
                _issuer_cert_cache.pop(cache_key, None)
            return None
    path = _issuer_disk_cache_path(token_key, fp)
    try:
        with open(path, "rb") as f:
            disk_der = f.read()
    except OSError:
        return None
    if not disk_der:
        return None
    try:
        print("Usando certificado emisor en caché en disco (respaldo tras fallo de red o AIA).")
        cert = x509.load_der_x509_certificate(disk_der)
        if not _issuer_dn_matches_parent_candidate(lower_cert, cert):
            print("Caché en disco no coincide con el emisor esperado; se elimina.")
            try:
                os.remove(path)
            except OSError:
                pass
            return None
        with _issuer_cert_cache_lock:
            _issuer_cert_cache[cache_key] = disk_der
        return cert
    except ValueError as e_parse:
        print(f"Caché en disco inválida, se elimina: {e_parse}")
        try:
            os.remove(path)
        except OSError:
            pass
        return None


def _authority_key_extensions_consistent(lower: x509.Certificate, candidate_parent: x509.Certificate) -> bool:
    """Comprueba AKI del hijo frente a SKI y número de serie del padre cuando esas extensiones existen."""
    try:
        aki_ext = lower.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_KEY_IDENTIFIER)
    except x509.ExtensionNotFound:
        return True

    aki = aki_ext.value

    if aki.key_identifier is not None:
        try:
            ski_ext = candidate_parent.extensions.get_extension_for_oid(ExtensionOID.SUBJECT_KEY_IDENTIFIER)
        except x509.ExtensionNotFound:
            pass
        else:
            if ski_ext.value.digest != aki.key_identifier:
                return False

    if aki.authority_cert_serial_number is not None:
        if candidate_parent.serial_number != aki.authority_cert_serial_number:
            return False

    return True


def _issuer_dn_matches_parent_candidate(lower: x509.Certificate, candidate_parent: x509.Certificate) -> bool:
    return candidate_parent.subject == lower.issuer and _authority_key_extensions_consistent(lower, candidate_parent)


def _fetch_issuer_from_service(token_key: str | None, lower_cert: x509.Certificate) -> x509.Certificate | None:
    url = os.environ.get("TUQUITO_ISSUER_SERVICE_URL", "").strip()
    if not url:
        return None
    try:
        child_b64 = b64encode(lower_cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
        response = post(
            url,
            json={"childCertificate": child_b64},
            timeout=15,
            headers={"Content-Type": "application/json"},
        )
    except requests_exceptions.RequestException as e_req:
        print(f"Error de red al obtener emisor desde el servicio Tuquito: {e_req}")
        return None
    if response.status_code == 404:
        return None
    if response.status_code != 200:
        print(f"Servicio de emisor respondió HTTP {response.status_code}: {response.text[:200]!r}")
        return None
    try:
        payload = response.json()
    except ValueError:
        print("Respuesta del servicio de emisor no es JSON válido.")
        return None
    if not payload.get("status"):
        return None
    b64_issuer = payload.get("issuerCertificate")
    if not b64_issuer or not isinstance(b64_issuer, str):
        return None
    try:
        try:
            issuer_der = b64decode(b64_issuer, validate=True)
        except TypeError:
            issuer_der = b64decode(b64_issuer)
    except Exception:
        print("issuerCertificate del servicio no es base64 válido.")
        return None
    try:
        issuer = x509.load_der_x509_certificate(issuer_der)
    except ValueError:
        print("No se pudo parsear el certificado emisor devuelto por el servicio.")
        return None
    if not _issuer_dn_matches_parent_candidate(lower_cert, issuer):
        print("El emisor devuelto por el servicio no coincide con el certificado hijo; se ignora.")
        return None
    print("Usando certificado emisor obtenido del servidor de aplicación (TUQUITO_ISSUER_SERVICE_URL).")
    _store_issuer_cache(token_key, lower_cert, issuer_der)
    return issuer


def _resolve_issuer_fallback(token_key: str | None, lower_cert: x509.Certificate) -> x509.Certificate | None:
    cached = _load_issuer_from_cache(token_key, lower_cert)
    if cached:
        return cached
    return _fetch_issuer_from_service(token_key, lower_cert)


def get_issuer_cert(cert: x509.Certificate, token_key: str | None = None) -> x509.Certificate:
    """
    Obtiene el certificado emisor de un certificado dado utilizando la extensión AIA.
    Intenta todas las URLs de CA_ISSUERS disponibles como fallback.
    Si token_key está definido, guarda en caché el emisor obtenido con éxito (memoria y disco; clave: token + huella del cert inferior)
    y lo usa como respaldo si las peticiones o la AIA fallan. Si no hay caché, consulta TUQUITO_ISSUER_SERVICE_URL (POST con childCertificate en base64).
    Devuelve un objeto x509.Certificate o levanta una CertificateError.
    """
    try:
        aia_ext = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia = aia_ext.value 
        
        # Recopilar todas las URLs de CA_ISSUERS
        issuer_urls = []
        for access_description in aia:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_urls.append(access_description.access_location.value)
        
        if not issuer_urls:
            fallback = _resolve_issuer_fallback(token_key, cert)
            if fallback:
                return fallback
            raise AIAExtensionNotFoundError("Descriptor CA_ISSUERS no encontrado en la extensión AIA.")
        
        # Intentar cada URL como fallback
        last_error = None
        for issuer_url in issuer_urls:
            print(f"Obteniendo certificado del emisor desde: {issuer_url}")
            try:
                response = get(issuer_url, timeout=10) 
                response.raise_for_status() 
                
                try:
                    issuer = x509.load_der_x509_certificate(response.content)
                    if token_key:
                        _store_issuer_cache(token_key, cert, issuer.public_bytes(serialization.Encoding.DER))
                    return issuer
                except ValueError: 
                    print("Error al parsear formato DER, intentando PEM...")
                    try:
                        issuer = x509.load_pem_x509_certificate(response.content)
                        if token_key:
                            _store_issuer_cache(token_key, cert, issuer.public_bytes(serialization.Encoding.DER))
                        return issuer
                    except ValueError as e_pem:
                        last_error = CertificateParsingError(f"No se pudo parsear el certificado desde {issuer_url} como DER ni PEM.", e_pem)
                        print(f"Error parseando desde {issuer_url}: {str(e_pem)}")
                        continue  # Intentar siguiente URL
            except requests_exceptions.RequestException as e_req:
                last_error = IssuerCertificateFetchError(f"Error de red al obtener certificado desde {issuer_url}.", e_req)
                print(f"Error de red desde {issuer_url}: {str(e_req)}")
                continue  # Intentar siguiente URL
        
        # Si llegamos aquí, todas las URLs fallaron: caché (memoria/disco) y servicio remoto antes del error
        fallback = _resolve_issuer_fallback(token_key, cert)
        if fallback:
            return fallback
        if last_error:
            raise last_error
        raise IssuerCertificateFetchError("No se pudo obtener el certificado del emisor desde ninguna URL disponible.")
        
    except x509.ExtensionNotFound:
        fallback = _resolve_issuer_fallback(token_key, cert)
        if fallback:
            return fallback
        raise AIAExtensionNotFoundError("Extensión AIA no encontrada en el certificado.")
    except CertificateError:
        raise  # Re-raise our custom errors as-is
    except Exception as e: 
        raise IssuerCertificateFetchError(f"Error inesperado al procesar AIA para obtener el emisor: {str(e)}", e) from e

def get_certificates_from_token(lib_path: str, pin: str) -> tuple[list[tuple[x509.Certificate, bytes]], PyKCS11.Session, x509.Name | None]:
    """
    Obtiene certificados de un token PKCS#11.
    Devuelve una tupla (lista_de_cert_data, sesión, subject_del_primer_certificado) o levanta una CertificateError.
    La sesión devuelta DEBE ser gestionada (logout/close) por el llamador.
    """
    pkcs11 = PyKCS11.PyKCS11Lib()
    try:
        print(f"Cargando biblioteca PKCS#11: {lib_path}")
        pkcs11.load(lib_path)
    except PyKCS11.PyKCS11Error as e_pkcs_load: 
        raise PKCS11LoadError(original_exception=e_pkcs_load) from e_pkcs_load
    except Exception as e_load: 
        raise PKCS11LoadError(original_exception=e_load) from e_load

    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        raise TokenNotFoundError()

    session = None
    try:
        session = pkcs11.openSession(slots[0], PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
        session.login(pin)
    except PyKCS11.PyKCS11Error as e_pkcs_session:
        error_type = None
        if hasattr(e_pkcs_session, 'rc'):
            if e_pkcs_session.rc == PyKCS11.CKR_PIN_INCORRECT:
                error_type = "BAD_PIN"
            elif e_pkcs_session.rc == PyKCS11.CKR_PIN_LOCKED:
                error_type = "PIN_LOCKED"
        if session and hasattr(session, 'is_valid') and not session.is_valid: 
            try:
                session.closeSession() 
            except PyKCS11.PyKCS11Error:
                print("Error al intentar cerrar sesión PKCS#11 ya inválida.")
        raise TokenLoginError(original_exception=e_pkcs_session, error_type=error_type) from e_pkcs_session
    except Exception as e_session: 
        if session and hasattr(session, 'is_valid') and not session.is_valid:
            try:
                session.closeSession()
            except PyKCS11.PyKCS11Error:
                print("Error al intentar cerrar sesión PKCS#11 ya inválida durante excepción genérica.")
        raise TokenLoginError(original_exception=e_session) from e_session

    cert_data_list = [] 
    first_cert_subject = None

    try:
        cert_template = [(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)]
        cert_attributes_to_get = [PyKCS11.CKA_VALUE, PyKCS11.CKA_SUBJECT]

        for cert_handle in session.findObjects(cert_template):
            try:
                retrieved_attrs = session.getAttributeValue(cert_handle, cert_attributes_to_get)
                cert_der = bytes(retrieved_attrs[0]) 
                
                cert = x509.load_der_x509_certificate(cert_der)
                print(f"Certificado encontrado en el token: {cert.subject}")
                cert_data_list.append((cert, cert_der))
                
                if not first_cert_subject:
                    first_cert_subject = cert.subject 
            except PyKCS11.PyKCS11Error as e_attr:
                print(f"Error obteniendo atributos para un objeto de certificado en el token: {e_attr}")
            except ValueError as e_parse: 
                print(f"Error parseando un certificado DER desde el token: {e_parse}")

        if not cert_data_list:
            print("No se encontraron certificados en el token.")
    except PyKCS11.PyKCS11Error as e_find:
        raise CertificateError(f"Error procesando certificados desde el token: {str(e_find)}", 500) from e_find
    
    return cert_data_list, session, first_cert_subject

def get_full_chain(cert: x509.Certificate, cert_der: bytes, token_key: str | None = None):
    """
    Construye la cadena de certificados completa.
    token_key: identificador estable del token (p. ej. ATR en hex) para caché de emisores.
    Devuelve una tupla (lista_de_cert_der, http_status_code) o 
    (respuesta_jsonify_de_error, http_status_code_de_error).
    """
    chain = [cert_der]
    current_cert = cert
    max_chain_depth = 10  

    try:
        while len(chain) < max_chain_depth:
            if current_cert.issuer == current_cert.subject:
                print("Certificado autofirmado alcanzado. Construcción de cadena completada.")
                return chain, 200 

            issuer_cert = get_issuer_cert(current_cert, token_key)
            issuer_cert_der = issuer_cert.public_bytes(serialization.Encoding.DER)

            if issuer_cert_der in chain:
                print("Certificado del emisor ya está en la cadena (bucle detectado). Finalizando cadena.")
                return chain, 200 
            
            chain.append(issuer_cert_der)
            print(f"Certificado del emisor encontrado y añadido: {issuer_cert.subject}")
            current_cert = issuer_cert
        
        print(f"Construcción de cadena detenida: profundidad máxima de cadena ({max_chain_depth}) alcanzada.")
        return jsonify({"status": False, "message": f"No se pudo construir la cadena completa (límite de profundidad {max_chain_depth} alcanzado)."}), 500
    except CertificateError as e: 
        print(f"Error construyendo la cadena de certificados: {e.message} (Código: {e.status_code})")
        return jsonify({"status": False, "message": e.message}), e.status_code
    except Exception as e_unhandled: 
        error_message = f"Error inesperado y no controlado en la construcción de la cadena: {str(e_unhandled)}"
        print(error_message)
        return jsonify({"status": False, "message": error_message}), 500

def cert_to_base64(cert_der: bytes) -> str:
    """Convierte un certificado DER a formato base64 string."""
    return b64encode(cert_der).decode('ascii')
