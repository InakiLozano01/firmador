# Emisor por servidor: TUQUITO_ISSUER_SERVICE_URL en el entorno o en .env junto al .exe (ver client_env).
##################################################
###              Imports externos              ###
##################################################

from base64 import b64decode, b64encode
import os
import re
import sys
import time
from requests import get, post, exceptions as requests_exceptions # Explicit import for requests exceptions
import threading
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import dsa, ec, ed25519, ed448, padding, rsa
from flask import jsonify

from client_env import load_client_dotenv
from diagnostics import log_event

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


class IssuerChainTimeoutError(CertificateError):
    def __init__(self, message="Se agotó el tiempo para construir la cadena de certificados."):
        super().__init__(message, 504)

class CertificateParsingError(CertificateError):
    """Error when parsing certificate data (DER/PEM)."""
    def __init__(self, message="Error al parsear el certificado.", original_exception=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message, 500)

##################################################
###          Certificate Functions             ###
##################################################

# Caché de certificados emisor (superiores) por token (p. ej. ATR hex) y huella del certificado inferior.
_issuer_cert_cache: dict[tuple[str, str], bytes] = {}
_issuer_cert_cache_lock = threading.Lock()


def _client_base_dir() -> str:
    if getattr(sys, "frozen", False):
        user_config_root = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(user_config_root, "Tuquito")
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


def _log_issuer_cache_lookup(
    *,
    found: bool,
    source: str | None = None,
    reason: str | None = None,
    token_key: str | None = None,
    child_fingerprint: str | None = None,
) -> None:
    fields = {
        "found": found,
        "stage": "before_network",
    }
    if source is not None:
        fields["source"] = source
    if reason is not None:
        fields["reason"] = reason
    if token_key is not None:
        fields["token_key"] = token_key
    if child_fingerprint is not None:
        fields["child_fingerprint"] = child_fingerprint
    log_event("issuer_cache_hit" if found else "issuer_cache_miss", **fields)


def _load_issuer_from_cache(token_key: str | None, lower_cert: x509.Certificate) -> x509.Certificate | None:
    if not token_key:
        _log_issuer_cache_lookup(found=False, reason="no_token_key")
        return None
    fp = _lower_cert_fingerprint_hex(lower_cert)
    cache_key = (token_key, fp)
    with _issuer_cert_cache_lock:
        cached_der = _issuer_cert_cache.get(cache_key)
    if cached_der:
        try:
            print("Usando certificado emisor en caché en memoria; se omite la consulta de red.")
            c_mem = x509.load_der_x509_certificate(cached_der)
            if not _issuer_dn_matches_parent_candidate(lower_cert, c_mem):
                print("Caché en memoria no coincide con el emisor esperado; se elimina.")
                with _issuer_cert_cache_lock:
                    _issuer_cert_cache.pop(cache_key, None)
                _log_issuer_cache_lookup(
                    found=False,
                    source="memory",
                    reason="dn_mismatch",
                    token_key=token_key,
                    child_fingerprint=fp,
                )
                return None
            _log_issuer_cache_lookup(
                found=True,
                source="memory",
                token_key=token_key,
                child_fingerprint=fp,
            )
            return c_mem
        except ValueError as e_parse:
            print(f"Entrada de caché en memoria inválida, se elimina: {e_parse}")
            with _issuer_cert_cache_lock:
                _issuer_cert_cache.pop(cache_key, None)
            _log_issuer_cache_lookup(
                found=False,
                source="memory",
                reason="invalid",
                token_key=token_key,
                child_fingerprint=fp,
            )
            return None
    path = _issuer_disk_cache_path(token_key, fp)
    try:
        with open(path, "rb") as f:
            disk_der = f.read()
    except OSError:
        _log_issuer_cache_lookup(
            found=False,
            reason="not_found",
            token_key=token_key,
            child_fingerprint=fp,
        )
        return None
    if not disk_der:
        _log_issuer_cache_lookup(
            found=False,
            reason="not_found",
            token_key=token_key,
            child_fingerprint=fp,
        )
        return None
    try:
        print("Usando certificado emisor en caché en disco; se omite la consulta de red.")
        cert = x509.load_der_x509_certificate(disk_der)
        if not _issuer_dn_matches_parent_candidate(lower_cert, cert):
            print("Caché en disco no coincide con el emisor esperado; se elimina.")
            try:
                os.remove(path)
            except OSError:
                pass
            _log_issuer_cache_lookup(
                found=False,
                source="disk",
                reason="dn_mismatch",
                token_key=token_key,
                child_fingerprint=fp,
            )
            return None
        with _issuer_cert_cache_lock:
            _issuer_cert_cache[cache_key] = disk_der
        _log_issuer_cache_lookup(
            found=True,
            source="disk",
            token_key=token_key,
            child_fingerprint=fp,
        )
        return cert
    except ValueError as e_parse:
        print(f"Caché en disco inválida, se elimina: {e_parse}")
        try:
            os.remove(path)
        except OSError:
            pass
        _log_issuer_cache_lookup(
            found=False,
            source="disk",
            reason="invalid",
            token_key=token_key,
            child_fingerprint=fp,
        )
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
    if candidate_parent.subject != lower.issuer:
        return False
    if not _authority_key_extensions_consistent(lower, candidate_parent):
        return False

    try:
        basic_constraints = candidate_parent.extensions.get_extension_for_oid(
            ExtensionOID.BASIC_CONSTRAINTS
        ).value
        if not basic_constraints.ca:
            return False
    except x509.ExtensionNotFound:
        return False

    try:
        key_usage = candidate_parent.extensions.get_extension_for_oid(
            ExtensionOID.KEY_USAGE
        ).value
        if not key_usage.key_cert_sign:
            return False
    except x509.ExtensionNotFound:
        pass

    public_key = candidate_parent.public_key()
    try:
        if isinstance(public_key, rsa.RSAPublicKey):
            algorithm_parameters = getattr(lower, "signature_algorithm_parameters", None)
            signature_padding = (
                algorithm_parameters
                if isinstance(algorithm_parameters, padding.AsymmetricPadding)
                else padding.PKCS1v15()
            )
            public_key.verify(
                lower.signature,
                lower.tbs_certificate_bytes,
                signature_padding,
                lower.signature_hash_algorithm,
            )
        elif isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(
                lower.signature,
                lower.tbs_certificate_bytes,
                ec.ECDSA(lower.signature_hash_algorithm),
            )
        elif isinstance(public_key, dsa.DSAPublicKey):
            public_key.verify(
                lower.signature,
                lower.tbs_certificate_bytes,
                lower.signature_hash_algorithm,
            )
        elif isinstance(public_key, (ed25519.Ed25519PublicKey, ed448.Ed448PublicKey)):
            public_key.verify(lower.signature, lower.tbs_certificate_bytes)
        else:
            return False
    except Exception:
        return False
    return True


def _network_timeout(deadline: float | None, maximum: float) -> float:
    if deadline is None:
        return maximum
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise IssuerChainTimeoutError()
    return max(0.1, min(maximum, remaining))


def _fetch_issuer_from_service(
    token_key: str | None,
    lower_cert: x509.Certificate,
    deadline: float | None = None,
) -> x509.Certificate | None:
    url = os.environ.get("TUQUITO_ISSUER_SERVICE_URL", "").strip()
    if not url:
        return None
    try:
        child_b64 = b64encode(lower_cert.public_bytes(serialization.Encoding.DER)).decode("ascii")
        response = post(
            url,
            json={"childCertificate": child_b64},
            timeout=_network_timeout(deadline, 15),
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


def _resolve_issuer_fallback(
    token_key: str | None,
    lower_cert: x509.Certificate,
    deadline: float | None = None,
) -> x509.Certificate | None:
    return _fetch_issuer_from_service(token_key, lower_cert, deadline)


def get_issuer_cert(
    cert: x509.Certificate,
    token_key: str | None = None,
    deadline: float | None = None,
) -> x509.Certificate:
    """
    Obtiene el certificado emisor de un certificado dado.
    Orden: caché (memoria/disco) → URLs CA_ISSUERS de AIA → TUQUITO_ISSUER_SERVICE_URL.
    Si hay acierto en caché, no consulta la red. Los emisores obtenidos con éxito
    se guardan en caché (clave: token + huella del certificado inferior).
    Devuelve un objeto x509.Certificate o levanta una CertificateError.
    """
    try:
        cached = _load_issuer_from_cache(token_key, cert)
        if cached:
            return cached

        aia_ext = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia = aia_ext.value

        # Recopilar todas las URLs de CA_ISSUERS
        issuer_urls = []
        for access_description in aia:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_urls.append(access_description.access_location.value)

        if not issuer_urls:
            fallback = _resolve_issuer_fallback(token_key, cert, deadline)
            if fallback:
                return fallback
            raise AIAExtensionNotFoundError("Descriptor CA_ISSUERS no encontrado en la extensión AIA.")

        # Intentar cada URL como fallback
        last_error = None
        for issuer_url in issuer_urls:
            print(f"Obteniendo certificado del emisor desde: {issuer_url}")
            try:
                response = get(
                    issuer_url,
                    timeout=_network_timeout(deadline, 10),
                )
                response.raise_for_status()

                try:
                    issuer = x509.load_der_x509_certificate(response.content)
                    if not _issuer_dn_matches_parent_candidate(cert, issuer):
                        print(f"El certificado obtenido desde {issuer_url} no es un emisor válido.")
                        continue
                    if token_key:
                        _store_issuer_cache(token_key, cert, issuer.public_bytes(serialization.Encoding.DER))
                    return issuer
                except ValueError:
                    print("Error al parsear formato DER, intentando PEM...")
                    try:
                        issuer = x509.load_pem_x509_certificate(response.content)
                        if not _issuer_dn_matches_parent_candidate(cert, issuer):
                            print(f"El certificado obtenido desde {issuer_url} no es un emisor válido.")
                            continue
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

        # Si llegamos aquí, todas las URLs AIA fallaron: servicio remoto (la caché ya se consultó al inicio)
        fallback = _resolve_issuer_fallback(token_key, cert, deadline)
        if fallback:
            return fallback
        if last_error:
            raise last_error
        raise IssuerCertificateFetchError("No se pudo obtener el certificado del emisor desde ninguna URL disponible.")

    except x509.ExtensionNotFound:
        fallback = _resolve_issuer_fallback(token_key, cert, deadline)
        if fallback:
            return fallback
        raise AIAExtensionNotFoundError("Extensión AIA no encontrada en el certificado.")
    except CertificateError:
        raise  # Re-raise our custom errors as-is
    except Exception as e:
        raise IssuerCertificateFetchError(f"Error inesperado al procesar AIA para obtener el emisor: {str(e)}", e) from e

def get_full_chain(
    cert: x509.Certificate,
    cert_der: bytes,
    token_key: str | None = None,
    max_duration_seconds: float = 20,
):
    """
    Construye la cadena de certificados completa.
    token_key: identificador estable del token (p. ej. ATR en hex) para caché de emisores.
    Devuelve una tupla (lista_de_cert_der, http_status_code) o
    (respuesta_jsonify_de_error, http_status_code_de_error).
    """
    chain = [cert_der]
    current_cert = cert
    max_chain_depth = 10
    deadline = time.monotonic() + max_duration_seconds

    try:
        while len(chain) < max_chain_depth:
            if time.monotonic() >= deadline:
                raise IssuerChainTimeoutError()
            if current_cert.issuer == current_cert.subject:
                print("Certificado autofirmado alcanzado. Construcción de cadena completada.")
                return chain, 200

            issuer_cert = get_issuer_cert(
                current_cert,
                token_key,
                deadline=deadline,
            )
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
