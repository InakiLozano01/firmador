##################################################
###              Imports externos              ###
##################################################

from base64 import b64encode
from requests import get
import PyKCS11
from cryptography import x509
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
from cryptography.hazmat.primitives import serialization
from flask import jsonify

def get_issuer_cert(cert):
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        for access_description in aia:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_url = access_description.access_location.value
                print(f"Obteniendo certificado del emisor desde: {issuer_url}")
                response = get(issuer_url)
                try:
                    return x509.load_der_x509_certificate(response.content), 200
                except ValueError:
                    print("Error al parsear formato DER, intentando PEM...")
                    return x509.load_pem_x509_certificate(response.content), 200
    except x509.ExtensionNotFound:
        return jsonify({"status": False, "message": "No se encontró la extensión de Información de Acceso a la Autoridad."}), 404
    except Exception as e:
        return jsonify({"status": False, "message": f"Error al obtener el certificado del emisor: {str(e)}"}), 500

def get_certificates_from_token(lib_path, pin, slot_index):
    pkcs11 = PyKCS11.PyKCS11Lib()
    try:
        pkcs11.load(lib_path)
    except Exception as e:
        return jsonify({"status": False, "message": f"Error al cargar la biblioteca PKCS#11: {str(e)}"}), 500

    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        return jsonify({"status": False, "message": "No se encontraron tokens."}), 404

    session = pkcs11.openSession(slots[slot_index], PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
    session.login(pin)

    cert_attributes = [PyKCS11.CKA_CLASS, PyKCS11.CKA_CERTIFICATE_TYPE, PyKCS11.CKA_VALUE]
    certificates = []

    for obj in session.findObjects():
        attributes = session.getAttributeValue(obj, cert_attributes)
        if attributes[0] == PyKCS11.CKO_CERTIFICATE:
            cert_der = bytes(attributes[2])
            cert = x509.load_der_x509_certificate(cert_der)
            print(f"Certificado encontrado en el token: {cert.subject}")
            certificates.append((cert, cert_der))
    return certificates, session, 200 

def get_full_chain(cert, cert_der):
    chain = [cert_der]
    current_cert = cert
    while True:
        if current_cert.issuer == current_cert.subject:
            print("Certificado autofirmado alcanzado. Construcción de cadena completada.")
            break
        issuer_cert, code = get_issuer_cert(current_cert)
        if code != 200:
            return jsonify({"status": False, "message": "Error al obtener el certificado del emisor."}), 500
        if issuer_cert is None:
            print("No se pudo obtener automáticamente el certificado del emisor. Saliendo de la construcción de cadena.")
            break
        issuer_cert_der = issuer_cert.public_bytes(serialization.Encoding.DER)
        if issuer_cert_der in chain:
            break  # Evitar bucles
        chain.append(issuer_cert_der)
        print(f"Certificado del emisor encontrado: {issuer_cert.subject}")
        current_cert = issuer_cert
    return chain

def cert_to_base64(cert_der):
    return b64encode(cert_der).decode('ascii')
