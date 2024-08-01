##################################################
###              Imports externos              ###
##################################################

from cryptography.hazmat.primitives import hashes
import json
import uuid
import platform
from flask import Flask, jsonify, request
import threading
from threading import Thread
import subprocess
import atexit
from flask_cors import CORS
import requests
import time as tiempo
from datetime import datetime
import pytz

##################################################
###              Imports propios               ###
##################################################

from tokenmg import *
from usbcard import *
from certificates import *
from digest import *
from imagecomp import *
from createimagetostamp import *

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################

app = Flask(__name__)
CORS(app)

java_process = None
java_process_started = False

##################################################
###     Inicializacion de servicio de digest   ###
##################################################

@app.before_request
def start_java_process():
    global java_process_started
    global java_process

    try:
        response = requests.get("http://localhost:8080/services/rest/serviceStatus")
        if response.status_code == 200 and response.text == "OK":
            java_process_started = True
    except Exception as e:
        pass

    if not java_process_started:
        print("Starting Java process...")
        try:
            java_process = subprocess.Popen(['java', '-jar', r'C:\Users\kakit\OneDrive\Downloads\Projects\Firmador\firmar_python\firma_cliente\dssapp\dss-demo-webapp\target\dss-signature-rest-6.1.RC1.jar'])
            java_process_started = True
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error al iniciar el proceso Java: {str(e)}"}), 500

        # Ensure Java process is terminated when Flask app shuts down
        def cleanup():
            java_process.terminate()

        atexit.register(cleanup)

##################################################
###     Rutas de la aplicacion para Tapir      ###
##################################################

@app.route('/rest/certificates', methods=['POST'])
def get_certificates():
    try:
        # Get the JSON data from the request
        data = request.get_json()
        if not data or 'pdfs' not in data:
            return jsonify({"status": "error", "message": "No se recibieron archivos PDF."}), 400

        pdfs = data['pdfs']
        if not isinstance(pdfs, list) or pdfs is None:
            return jsonify({"status": "error", "message": "El campo 'pdfs' debe ser una lista."}), 400
        
        fields = data['fields']
        if not isinstance(fields, list) or fields is None:
            return jsonify({"status": "error", "message": "El campo 'fields' debe ser una lista."}), 400
        
        names = data['names']
        if not isinstance(names, list) or names is None:
            return jsonify({"status": "error", "message": "El campo 'names' debe ser una lista."}), 400
        
        stamps = data['stamps']
        if not isinstance(stamps, list) or stamps is None:
            return jsonify({"status": "error", "message": "El campo 'stamps' debe ser una lista."}), 400
        
        areas = data['areas']
        if not isinstance(areas, list) or areas is None:
            return jsonify({"status": "error", "message": "El campo 'areas' debe ser una lista."}), 400

        # Load token library mapping
        token_library_mapping = load_token_library_mapping()

        # List tokens
        token_info, code = list_tokens()
        if not token_info or code != 200:
            return jsonify({"status": "error", "message": "Error al listar tokens."}), 404

        # Slot selection logic
        selected_slot = []
        thread = threading.Thread(target=select_token_slot, args=(token_info, selected_slot))
        thread.start()
        thread.join()

        if not selected_slot:
            return jsonify({"status": "error", "message": "No se seleccionó ningún slot."}), 400

        selected_slot_index = selected_slot[0]
        token_unique_id, code = get_token_unique_id(token_info[selected_slot_index])
        if token_unique_id in token_library_mapping and code == 200:
            lib_path = token_library_mapping[token_unique_id]
        else:
            lib_path, code = select_library_file()
            if not lib_path or code != 200:
                return jsonify({"status": "error", "message": "No se seleccionó ninguna biblioteca."}), 400
            token_library_mapping[token_unique_id] = lib_path
            try:
                message, code = save_token_library_mapping(token_library_mapping)
                if code != 200:
                    return jsonify({"status": "error", "message": message}), code
            except Exception as e:
                return jsonify({"status": "error", "message": f"Error al guardar el mapeo de bibliotecas de tokens: {str(e)}"}), 500

        pin, code = get_pin_from_user()
        if not pin or code != 200:
            return jsonify({"status": "error", "message": "Entrada de PIN cancelada."}), 400

        certificates, code = get_certificates_from_token(lib_path, pin, selected_slot_index)
        if not certificates or code != 200:
            return jsonify({"status": "error", "message": "Problema al traer certificados del token."}), 404

        # Certificate selection logic
        selected_cert = []
        thread = threading.Thread(target=select_certificate, args=(certificates, selected_cert))
        thread.start()
        thread.join()

        if not selected_cert:
            return jsonify({"status": "error", "message": "No se seleccionó ningún certificado."}), 400

        selected_index = selected_cert[0]
        cert, cert_der = certificates[selected_index]
        cert_chain = get_full_chain(cert, cert_der)
        chain_base64 = [cert_to_base64(c) for c in cert_chain]

        response = {
            "status": "success",
            "response": {
                "tokenId": {
                    "id": str(uuid.uuid4())
                },
                "keyId": cert.fingerprint(hashes.SHA256()).hex().upper(),
                "certificate": cert_to_base64(cert_der),
                "certificateChain": chain_base64,
                "encryptionAlgorithm": "RSA"
            },
            "feedback": {
                "info": {
                    "language": "Python & Java",
                    "osName": platform.system(),
                    "osArch": platform.machine(),
                    "osVersion": platform.version(),
                    "arch": platform.architecture()[0],
                    "os": platform.system().upper()
                },
                "firmaCliente": "0.1"
            }
        }

        certificate = response["response"]["certificate"]
        certificate_chain = response["response"]["certificateChain"]

        data_to_sign_list = []

        for pdf in pdfs:
            for field, name, stamp, area in zip(fields, names, stamps, areas):
                encoded_image = encode_image("logo_tribunal_para_tapir_250px.png")
                current_time = int(tiempo.time() * 1000)
                datetimesigned = datetime.now(pytz.utc).astimezone(pytz.timezone('America/Argentina/Buenos_Aires')).strftime("%Y-%m-%d %H:%M:%S")
                custom_image = create_signature_image(
                        f"{name}\n{datetimesigned}\n{stamp}\n{area}",
                        encoded_image,
                        "token"
                    )
                data_to_sign_response = digestpdf(pdf, certificate, certificate_chain, stamp, field, custom_image, current_time)
                data_to_sign = data_to_sign_response['bytes']
                data_to_sign_list.append(data_to_sign)
        

        
        responsejson = json.loads(json.dumps(response))

        return jsonify(responsejson), 200
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"status": "error", "message": f"Error de PyKCS11: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error inesperado en get_certificates: {str(e)}"}), 500


if __name__ == "__main__":
    try:
        response = requests.get("http://localhost:8080/services/rest/serviceStatus")
        if response.status_code == 200 and response.text == "OK":
            java_process_started = True
    except Exception as e:
        pass

    if not java_process_started:
        print("Starting Java process...")
        try:
            java_process = subprocess.Popen(['java', '-jar', r'C:\Users\kakit\OneDrive\Downloads\Projects\Firmador\firmar_python\firma_cliente\dssapp\dss-demo-webapp\target\dss-signature-rest-6.1.RC1.jar'])
            java_process_started = True
        except Exception as e:
            print(f"Error al iniciar el proceso Java: {str(e)}")

    def cleanup():
        java_process.terminate()

    atexit.register(cleanup)

    app.run(host='127.0.0.1', port=9795)