import PyKCS11
import base64
from flask import jsonify

def get_private_key_and_certificate(session):
    """
    Retrieve the private key and certificate from the token session.
    """
    try:
        # Retrieve objects (private key and certificate)
        private_key_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)])
        certificate_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)])
        
        if not private_key_objects or not certificate_objects:
            return jsonify({"status": "error", "message": "No se encontraron claves privadas o certificados en el token."}), 404
        
        private_key = private_key_objects[0]
        
        return private_key
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"status": "error", "message": f"Error al obtener la clave privada: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al obtener la clave privada: {str(e)}"}), 500

def correct_base64_padding(data):
    """
    Correct the base64 padding of the given data.
    """
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += '=' * (4 - missing_padding)
    return data

def sign_data_with_private_key(session, private_key, data_to_sign_base64):
    """
    Sign the given data with the private key from the token session.
    """
    data_to_sign_base64 = correct_base64_padding(data_to_sign_base64)
    data_to_sign_bytes = base64.b64decode(data_to_sign_base64)
    
    mechanism = PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None)
    try:
        signature = bytes(session.sign(private_key, data_to_sign_bytes, mechanism))
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"status": "error", "message": f"Error al firmar los datos: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al firmar los datos: {str(e)}"}), 500
    
    # Convert the signature to base64 for sending to DSS
    signature_base64 = base64.b64encode(signature).decode("utf-8")
    return signature_base64, 200

def sign_multiple_data(session, data_to_sign_list):
    """
    Sign multiple data items using the private key from the token session.
    """
    try:
        private_key = get_private_key_and_certificate(session)
        
        signatures = []
        for data_to_sign_base64 in data_to_sign_list:
            signature_base64, code = sign_data_with_private_key(session, private_key, data_to_sign_base64)
            if code != 200:
                return jsonify({"status": "error", "message": "Error al firmar los datos."}), code
            signatures.append(signature_base64)
        
        return signatures, 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al firmar los datos: {str(e)}"}), 500