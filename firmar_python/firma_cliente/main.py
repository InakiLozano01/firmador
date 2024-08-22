##################################################
###              Imports externos              ###
##################################################

import json
import platform
from cryptography.hazmat.primitives import hashes
from uuid import uuid4
from flask import Flask, jsonify, request
from threading import Thread
from flask_cors import CORS
import os
import pystray
from pystray import MenuItem
from PIL import Image

##################################################
###              Imports propios               ###
##################################################

from tokenmg import *
from certificates import *
from digest import *
from imagecomp import *
from createimagetostamp import *
from signing import *
from interfaz import *

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################

app = Flask(__name__)
CORS(app)

##################################################
###                 Endpoints                  ###
##################################################

@app.route('/rest/certificates', methods=['GET'])
def get_certificates():
    global pin, lib_path, selected_slot_index

    try:

        current_file_path = os.path.abspath(__file__)
        if 'temp' not in current_file_path.lower():
            mode = 'python'
        else:
            mode = 'exe'

        # Carga el mapeo de drivers previamente usados
        token_library_mapping, code = load_token_library_mapping()

        # Listar los tokens conectados
        token_info, code = list_tokens()
        if not token_info or code != 200:
            return jsonify({"status": False, "message": "Error al listar tokens."}), 404

        # Seleccionar el slot del token
        selected_slot = []
        thread_slot = Thread(target=select_token_slot, args=(token_info, selected_slot, mode))
        thread_slot.start()
        thread_slot.join()

        if not selected_slot:
            return jsonify({"status": False, "message": "No se seleccionó ningún slot."}), 400

        selected_slot_index = selected_slot[0]

        # Cotejamos el nombre del token para determinar el driver a utilizar
        token_unique_id, token_name, code = get_token_unique_id(token_info[selected_slot_index])
        if token_name in token_library_mapping:
            lib_path = token_library_mapping[token_name]
        else:
            lib_path, code = select_library_file()
            if not lib_path:
                return jsonify({True: False, "message": "No se seleccionó ninguna biblioteca."}), 400
            token_library_mapping[token_name] = lib_path
            try:
                message, code = save_token_library_mapping(token_library_mapping)
                if code != 200:
                    return jsonify({"status": False, "message": message}), code
            except Exception as e:
                return jsonify({"status": False, "message": f"Error al guardar el mapeo de bibliotecas de tokens: {str(e)}"}), 500

        # Ingresar el PIN del token
        pin, code = get_pin_from_user(mode)
        if not pin or code != 200:
            return jsonify({"status": False, "message": "Entrada de PIN cancelada."}), 400

        # Obtener los certificados del token
        certificates, session, code = get_certificates_from_token(lib_path, pin, selected_slot_index)
        if not certificates or code != 200:
            return jsonify({"status": False, "message": "Problema al traer certificados del token."}), 404

        # Seleccionar el certificado alojado en el token
        selected_cert = []
        thread_cert = Thread(target=select_certificate, args=(certificates, selected_cert, mode))
        thread_cert.start()
        thread_cert.join()

        if not selected_cert:
            return jsonify({"status": False, "message": "No se seleccionó ningún certificado."}), 400

        selected_index = selected_cert[0]
        cert, cert_der = certificates[selected_index]

        # Obtener la cadena de certificados completa
        cert_chain = get_full_chain(cert, cert_der)
        chain_base64 = [cert_to_base64(c) for c in cert_chain]

        response = {
            "status": True,
            "response": {
                "tokenId": {
                    "id": str(uuid4())
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

        responsejson = json.loads(json.dumps(response))

        return jsonify(responsejson), 200
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"status": False, "message": f"Error de PyKCS11: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"status": False, "message": f"Error inesperado en get_certificates: {str(e)}"}), 500
    
@app.route('/rest/sign', methods=['POST'])
def get_signatures():
    global pin, lib_path, selected_slot_index

    try:
        data = request.get_json()
        if not data or 'data_to_sign_list' not in data:
            return jsonify({"status": False, "message": "No se recibieron datos para firmar."}), 400
        
        data_to_sign_list = data['data_to_sign_list']
        if not data_to_sign_list or not isinstance(data_to_sign_list, list):
            return jsonify({"status": False, "message": "Lista de datos a firmar vacía."}), 400
        
        certificates, session, code = get_certificates_from_token(lib_path, pin, selected_slot_index)
        if not certificates or code != 200:
            return jsonify({"status": False, "message": "Problema al traer certificados del token."}), 404
        
        signatures, code = sign_multiple_data(session, data_to_sign_list)
        if code != 200:
            return jsonify({"status": False, "message": "Error al firmar los datos."}), code
        
        response = {
            "status": True,
            "response": {
                "signatures": signatures
            }
        }

        responsejson = json.loads(json.dumps(response))
        return jsonify(responsejson), 200
    
    except Exception as e:
        return jsonify({"status": False, "message": "Error inesperado en get_signatures." + str(e)}), 500

def run_flask_app():
    app.run(host='127.0.0.1', port=9795, threaded=True)

def on_quit(icon, item):
    icon.stop()
    os._exit(0)

def setup(icon):
    icon.visible = True

# Create an icon for the system tray
def run_tray_icon():
    current_file_path = os.path.abspath(__file__)
    if 'temp' not in current_file_path.lower():
        image = './images/app_icon_dragon.png'
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        image = os.path.join(exe_dir, 'app_icon_dragon.png')
    image = Image.open(image)  # Replace with the path to your icon image
    menu = (MenuItem('Salir...', on_quit),)
    icon = pystray.Icon("name", image, "SyraxApp", menu)
    icon.run(setup)

if __name__ == "__main__":

    tray_icon_thread = Thread(target=run_tray_icon)
    flask_thread = Thread(target=run_flask_app)

    tray_icon_thread.start()
    flask_thread.start()

    tray_icon_thread.join()
    flask_thread.join()