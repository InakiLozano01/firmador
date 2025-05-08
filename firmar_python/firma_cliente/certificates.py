##################################################
###              Imports externos              ###
##################################################

from base64 import b64encode
from requests import get, exceptions as requests_exceptions # Explicit import for requests exceptions
import PyKCS11
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
from cryptography.hazmat.primitives import serialization
from flask import jsonify

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

def get_issuer_cert(cert: x509.Certificate) -> x509.Certificate:
    """
    Obtiene el certificado emisor de un certificado dado utilizando la extensión AIA.
    Devuelve un objeto x509.Certificate o levanta una CertificateError.
    """
    try:
        aia_ext = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS)
        aia = aia_ext.value 
        for access_description in aia:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_url = access_description.access_location.value
                print(f"Obteniendo certificado del emisor desde: {issuer_url}")
                try:
                    response = get(issuer_url, timeout=10) 
                    response.raise_for_status() 
                    
                    try:
                        return x509.load_der_x509_certificate(response.content)
                    except ValueError: 
                        print("Error al parsear formato DER, intentando PEM...")
                        try:
                            return x509.load_pem_x509_certificate(response.content)
                        except ValueError as e_pem:
                            raise CertificateParsingError(f"No se pudo parsear el certificado desde {issuer_url} como DER ni PEM.", e_pem) from e_pem
                except requests_exceptions.RequestException as e_req:
                    raise IssuerCertificateFetchError(f"Error de red al obtener certificado desde {issuer_url}.", e_req) from e_req
        raise AIAExtensionNotFoundError("Descriptor CA_ISSUERS no encontrado en la extensión AIA.")
    except x509.ExtensionNotFound: 
        raise AIAExtensionNotFoundError("Extensión AIA no encontrada en el certificado.")
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

def get_full_chain(cert: x509.Certificate, cert_der: bytes):
    """
    Construye la cadena de certificados completa.
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

            issuer_cert = get_issuer_cert(current_cert) 
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
