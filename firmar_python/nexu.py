import requests
import logging
import base64
import re
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from errors import PDFSignatureError

def get_certificate_from_nexu(host):
    try:
        response = requests.get('http://'+ host +':50000/certificados')
        response.raise_for_status()
        certificatesjson = response.json()
        return certificatesjson
    except requests.RequestException as e:
        logging.error(f"Error in get_certificate_from_nexu: {str(e)}")
        raise PDFSignatureError("Failed to obtain certificate from NexU.")
    
def extract_certificate_info(cert_base64):
    try:
        cert_bytes = base64.b64decode(cert_base64)
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())

        # Extraer el nombre del sujeto
        subject = cert.subject.rfc4514_string()
        # Buscar el CUIL en el nombre del sujeto
        cuil = cert.subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER)[0].value
        # Extraer nombre completo
        common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value

        # Extraer email (si existe)
        email = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.RFC822Name)

        cuil = re.sub(r'\D', '', cuil)
        email = email[0] if email else None

        return cuil, common_name, email
    except Exception as e:
        logging.error(f"Error al extraer información del certificado: {str(e)}")
        raise PDFSignatureError("Failed to extract certificate information.")
    
def get_signature_value(data_to_sign, certificate_data, host):
    try:
        body = {
            "tokenId": certificate_data['response']['tokenId'],
            "keyId": certificate_data['response']['keyId'],
            "toBeSigned": {"bytes": data_to_sign},
            "digestAlgorithm": "SHA256"
        }
        response = requests.post('http://' + host + ':50000/firmar', json=body)
        signjson = response.json()
        return signjson['response']['signatureValue']
    except requests.RequestException as e:
        logging.error(f"Error in get_signature_value: {str(e)}")
        raise PDFSignatureError("Failed to get signature value from NexU.")