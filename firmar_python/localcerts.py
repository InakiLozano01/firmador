from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
from cryptography import x509
import base64


def get_signature_value_own(data_to_sign):
    # Cargar la clave privada desde un archivo
    with open("C:/Users/kakit/OneDrive/Downloads/Projects/private_key.pem", "rb") as key_file:
        private_key = load_pem_private_key(key_file.read(), password=None, backend=default_backend())

    # Generar la firma
    signature = private_key.sign(
        data_to_sign,
        padding.PKCS1v15(),
        hashes.SHA256()
    )

    # Convertir la firma a base64 para enviarla a DSS
    signature_base64 = base64.b64encode(signature).decode("utf-8")
    return signature_base64

def get_certificate_from_local():
    # Leer el certificado desde un archivo
    with open("C:/Users/kakit/OneDrive/Downloads/Projects/certificate.pem", "rb") as cert_file:
        certificate_data = cert_file.read()
    cert = certificate_data
    cert_chain = [certificate_data]
    # Convertir el certificado a base64 para enviarlo a DSS
    certificate_base64 = {
        "certificate": cert,
        "certificateChain": cert_chain
    }
    return certificate_base64

def extract_certificate_info_own(cert_base64):
    # Extraer el nombre del sujeto
    subject = cert_base64.subject.rfc4514_string()
    # Extraer nombre completo
    common_name = subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value

    # Extraer email (si existe)
    email = cert_base64.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.RFC822Name)

    email = email[0] if email else None

    return common_name, email
