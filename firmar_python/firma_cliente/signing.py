import PyKCS11
from base64 import b64encode, b64decode
from flask import jsonify

def get_private_key_and_certificate(session):
    """
    Recupera la clave privada y el certificado de la sesion.
    """
    try:
        # Recuperar objetos (clave privada y certificado)
        private_key_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)])
        certificate_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)])
        
        if not private_key_objects or not certificate_objects:
            return jsonify({"status": "error", "message": "No se encontraron claves privadas o certificados en la sesion."}), 404
        
        private_key = private_key_objects[0]
        
        return private_key
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"status": "error", "message": f"Error al obtener la clave privada: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al obtener la clave privada: {str(e)}"}), 500

def correct_base64_padding(data):
    """
    Correcion del pading en base64 de los datos.
    """
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += '=' * (4 - missing_padding)
    return data

def sign_data_with_private_key(session, private_key, data_to_sign_base64):
    """
    Firma los datos con la clave privada recuperada de la sesion.
    """
    data_to_sign_base64 = correct_base64_padding(data_to_sign_base64)
    data_to_sign_bytes = b64decode(data_to_sign_base64)
    
    mechanism = PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None)
    try:
        signature = bytes(session.sign(private_key, data_to_sign_bytes, mechanism))
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"status": "error", "message": f"Error al firmar los datos: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al firmar los datos: {str(e)}"}), 500
    
    # Convertir la firma a base64 para enviar a DSS
    signature_base64 = b64encode(signature).decode("utf-8")
    return signature_base64, 200

def sign_multiple_data(session, data_to_sign_list):
    """
    Firmar datos multiples usando la clave privada recuperada de la sesion.
    """
    try:
        private_key = get_private_key_and_certificate(session)
        
        signatures = []
        for data_to_sign_base64 in data_to_sign_list:
            signature_base64, code = sign_data_with_private_key(session, private_key, data_to_sign_base64)
            if code != 200:
                session.logout()
                session.closeSession()
                return jsonify({"status": "error", "message": "Error al firmar los datos."}), code
            signatures.append(signature_base64)
        
        session.logout()
        session.closeSession()
        
        return signatures, 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al firmar los datos: {str(e)}"}), 500