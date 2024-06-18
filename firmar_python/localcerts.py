from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
import base64
import os
from dotenv import load_dotenv

# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Obtener la contraseña de la clave privada desde las variables de entorno
private_key_password = os.getenv('password')

def get_signature_value_own(data_to_sign):
    # Cargar la clave privada desde un archivo
    with open("./private_key.pem", "rb") as key_file:
        private_key = load_pem_private_key(key_file.read(), password=private_key_password.encode(), backend=default_backend())

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
    with open("./certificate.pem", "rb") as cert_file:
        certificate_data = cert_file.read()

    # Convertir el certificado a base64 para enviarlo a DSS
    cert_base64 = base64.b64encode(certificate_data).decode("utf-8")
    cert_chain_base64 = [cert_base64]  # Asumiendo un solo elemento de cadena de certificado para simplificar

    certificate_base64 = {
        "certificate": cert_base64,
        "certificateChain": cert_chain_base64
    }
    return certificate_base64