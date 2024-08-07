# Description: Módulo para extraer información de un certificado X.509

import logging
import base64
import re
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from errors import PDFSignatureError
from flask import jsonify

###    Funcion para extraer toda la informacion de un certificado X.509 (nombre, cuil y email)    ###
def extract_certificate_info(cert_base64):
    try:
        cert_bytes = base64.b64decode(cert_base64)
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())

        # Buscar el CUIL en el nombre del sujeto
        cuil = cert.subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER)[0].value
        # Extraer nombre completo
        common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value

        # Extraer email (si existe)
        email = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.RFC822Name)

        cuil = re.sub(r'\D', '', cuil)
        email = email[0] if email else None

        return cuil, common_name, email, 200
    except Exception as e:
        logging.error(f"Error al extraer información del certificado: {str(e)}")
        raise jsonify({"status": False, "message": "Failed to extract certificate information."}), 400
    
###    Funcion para extraer el nombre de un certificado X.509    ###
def extract_certificate_info_name(cert_base64):
    try:
        cert_bytes = base64.b64decode(cert_base64)
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())

        # Extraer nombre completo
        common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value

        return common_name, 200
    except Exception as e:
        logging.error(f"Error al extraer información del certificado: {str(e)}")
        return jsonify({"status": False, "message": "Failed to extract certificate name information."}), 400