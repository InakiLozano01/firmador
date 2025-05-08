import PyKCS11
from base64 import b64encode, b64decode
import binascii # For Base64 decoding errors
from typing import Any # Import Any for more flexible type hinting if needed

##################################################
###         Custom Signing Exceptions          ###
##################################################

class SigningError(Exception):
    """Base class for signing related errors."""
    def __init__(self, message, status_code=500, original_exception=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message)
        self.message = full_message
        self.status_code = status_code

class KeyOrCertificateNotFoundError(SigningError):
    """Error when private key or certificate objects are not found in the session."""
    def __init__(self, message="No se encontraron claves privadas o certificados requeridos en la sesión.", status_code=404, original_exception=None):
        super().__init__(message, status_code, original_exception)

class PKCS11OperationError(SigningError):
    """Error during a specific PKCS#11 operation (e.g., sign, findObjects)."""
    pass

class InvalidBase64DataError(SigningError):
    """Error when base64 data is invalid or cannot be decoded."""
    def __init__(self, message="Error en la decodificación de datos Base64.", status_code=400, original_exception=None):
        super().__init__(message, status_code, original_exception)

##################################################
###            Signing Functions               ###
##################################################

def get_private_key_object(session: PyKCS11.Session) -> Any:
    """
    Recupera el primer objeto de clave privada de la sesión.
    Levanta KeyOrCertificateNotFoundError si no se encuentra, o PKCS11OperationError.
    Retorna un handle de objeto PKCS#11.
    """
    try:
        # Busca objetos de clave privada
        # Considerar si se necesita una búsqueda más específica (e.g., por CKA_LABEL)
        private_key_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)])
        
        if not private_key_objects:
            # También es importante verificar si hay certificados si son necesarios para la operación
            # Por ahora, nos centramos en la clave privada para la firma.
            raise KeyOrCertificateNotFoundError("No se encontraron objetos de clave privada en la sesión.")
        
        # Asumimos que la primera clave privada es la que se usará.
        # Si hay múltiples claves, se necesitaría una lógica de selección.
        return private_key_objects[0]
    except PyKCS11.PyKCS11Error as e:
        raise PKCS11OperationError("Error de PKCS#11 al obtener la clave privada.", original_exception=e) from e
    except Exception as e: # Captura general para errores inesperados
        raise SigningError("Error inesperado al obtener la clave privada.", original_exception=e) from e

def correct_base64_padding(data: str) -> str:
    """Asegura el padding correcto para datos Base64."""
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += '=' * (4 - missing_padding)
    return data

def sign_data_with_private_key(session: PyKCS11.Session, private_key_handle: Any, data_to_sign_base64: str) -> str:
    """
    Firma los datos proporcionados (en Base64) con la clave privada.
    Devuelve la firma en Base64 o levanta InvalidBase64DataError / PKCS11OperationError.
    'private_key_handle' es un handle de objeto PKCS#11.
    """
    try:
        padded_data_base64 = correct_base64_padding(data_to_sign_base64)
        data_to_sign_bytes = b64decode(padded_data_base64)
    except binascii.Error as e: # Catches BinasciiError for invalid base64
        raise InvalidBase64DataError(original_exception=e) from e
    except Exception as e: # Otras excepciones inesperadas durante la preparación de datos
        raise SigningError(f"Error inesperado preparando datos para firmar: {str(e)}", original_exception=e) from e
    
    # Definir el mecanismo de firma (SHA256 con RSA PKCS#1 v1.5)
    # Asegurarse que el token y la clave soportan este mecanismo.
    mechanism = PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None)
    
    try:
        signature_bytes = bytes(session.sign(private_key_handle, data_to_sign_bytes, mechanism))
    except PyKCS11.PyKCS11Error as e:
        raise PKCS11OperationError("Error de PKCS#11 al firmar los datos.", original_exception=e) from e
    except Exception as e: # Captura general para errores inesperados durante la firma
        raise SigningError("Error inesperado durante la operación de firma.", original_exception=e) from e
    
    # Convertir la firma binaria a Base64 string para la respuesta
    signature_base64 = b64encode(signature_bytes).decode("utf-8")
    return signature_base64

def sign_multiple_data_internal(session: PyKCS11.Session, data_to_sign_list: list[str]) -> list[str]:
    """
    Firma una lista de datos (strings Base64) usando la clave privada de la sesión.
    Importante: Esta función NO gestiona el logout/close de la sesión. El llamador es responsable.
    Devuelve una lista de firmas en Base64 o propaga excepciones.
    """
    # Obtener el handle de la clave privada. Esto puede levantar KeyOrCertificateNotFoundError o PKCS11OperationError.
    private_key_handle = get_private_key_object(session)
    
    signatures = []
    for data_base64 in data_to_sign_list:
        # sign_data_with_private_key puede levantar InvalidBase64DataError o PKCS11OperationError.
        signature_base64 = sign_data_with_private_key(session, private_key_handle, data_base64)
        signatures.append(signature_base64)
    
    return signatures