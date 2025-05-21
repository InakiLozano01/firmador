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
import psutil
import re
import PyKCS11
import multiprocessing

##################################################
###              Imports propios               ###
##################################################

from tokenmg import (
    load_token_library_mapping, save_token_library_mapping, 
    list_tokens_internal, get_token_unique_id_internal,
    TokenManagementError, TokenMappingError, SmartcardReaderError, 
    NoSmartcardFoundError, TokenATRReadError, TokenIdError
)
from certificates import (
    get_certificates_from_token, get_full_chain, cert_to_base64,
    CertificateError, AIAExtensionNotFoundError, IssuerCertificateFetchError, 
    CertificateParsingError, PKCS11LoadError, TokenNotFoundError as CertTokenNotFoundError,
    TokenLoginError as CertTokenLoginError
)
from signing import (
    sign_multiple_data_internal, 
    SigningError, KeyOrCertificateNotFoundError, PKCS11OperationError, InvalidBase64DataError
)
from interfaz import (
    select_token_slot, select_library_file, get_pin_from_user, select_certificate, show_alert
)

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################

app = Flask(__name__)
CORS(app)

##################################################
###                 Endpoints                  ###
##################################################

# Globals - Consider refactoring to pass as state or parameters in a future iteration
global_pin = None
global_lib_path = None
# selected_slot_index is not explicitly used as a global in the provided routes, but declared.

@app.route('/rest/certificates', methods=['GET'])
def get_certificates_route(): # Renamed to avoid conflict with certificates.py module
    global global_pin, global_lib_path
    session = None # Initialize session to None for the finally block

    try:
        current_file_path = os.path.abspath(__file__)
        mode = 'exe' if 'temp' in current_file_path.lower() else 'python'

        print(f"Mode: {mode}")

        try:
            token_library_mapping = load_token_library_mapping()
        except TokenMappingError as e:
            print(f"TokenMappingError in load_token_library_mapping: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code

        try:
            token_info_list = list_tokens_internal()
            if not token_info_list:
                return jsonify({"status": False, "message": "No se encontraron tokens o tarjetas en los lectores."}), 404
        except NoSmartcardFoundError as e:
            print(f"NoSmartcardFoundError in list_tokens_internal: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code
        except SmartcardReaderError as e:
            print(f"SmartcardReaderError in list_tokens_internal: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code
        
        # -------------------- SELECCIÓN DE TOKEN --------------------
        selected_slot_index = run_ui('select_token_slot', (token_info_list, mode))

        if selected_slot_index is None:
            return jsonify({"status": False, "message": "No se seleccionó ningún slot de token."}), 400

        selected_token_info = token_info_list[selected_slot_index]

        try:
            _token_unique_id, token_name = get_token_unique_id_internal(selected_token_info)
        except TokenIdError as e:
            print(f"TokenIdError in get_token_unique_id_internal: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code

        if token_name in token_library_mapping:
            global_lib_path = token_library_mapping[token_name]
        else:
            # select_library_file ahora se ejecuta en proceso separado
            chosen_lib_path = run_ui('select_library_file')
            if not chosen_lib_path:
                return jsonify({"status": False, "message": "No se seleccionó ninguna biblioteca de token o se canceló la selección."}), 400
            global_lib_path = chosen_lib_path
            token_library_mapping[token_name] = global_lib_path
            try:
                save_token_library_mapping(token_library_mapping)
            except TokenMappingError as e:
                print(f"TokenMappingError in save_token_library_mapping: {e.message}")
                return jsonify({"status": False, "message": e.message}), e.status_code
        
        # get_pin_from_user ahora se ejecuta en proceso separado
        pin_input = run_ui('get_pin_from_user', (mode,))
        if not pin_input: # Handles both cancellation and dialog setup errors from get_pin_from_user
            return jsonify({"status": False, "message": "Entrada de PIN cancelada o fallida."}), 400
        global_pin = pin_input

        try:
            certificates, session, subject_name = get_certificates_from_token(global_lib_path, global_pin)
        except CertTokenLoginError as e:
            print(f"CertTokenLoginError: {e.message}, Type: {e.error_type if hasattr(e, 'error_type') else 'N/A'}")
            if hasattr(e, 'error_type') and e.error_type == "BAD_PIN":
                return jsonify({"status": False, "message": "PIN incorrecto."}), 401
            return jsonify({"status": False, "message": e.message, "error_type": e.error_type if hasattr(e, 'error_type') else None}), e.status_code
        except (PKCS11LoadError, CertTokenNotFoundError, CertificateError) as e:
            print(f"Certificate/Token Error in get_certificates_from_token: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code
        
        if not certificates:
            return jsonify({"status": False, "message": "No se encontraron certificados en el token."}), 404

        # Prepare serializable certificate information for the UI
        serializable_certs_info = []
        for cert, _ in certificates:
            # Using RFC 4514 string representation of the subject, which is picklable
            # Alternatively, extract specific fields into a dictionary
            subject_str = cert.subject.rfc4514_string()
            serializable_certs_info.append(subject_str)

        selected_index = run_ui('select_certificate', (serializable_certs_info, mode))

        if selected_index is None:
            return jsonify({"status": False, "message": "No se seleccionó ningún certificado."}), 400
        
        user_selected_cert, user_selected_cert_der = certificates[selected_index]

        try:
            chain_result, chain_status_code = get_full_chain(user_selected_cert, user_selected_cert_der)
            if chain_status_code != 200:
                print(f"Error from get_full_chain (status {chain_status_code})")
                return chain_result, chain_status_code 
            chain_base64 = [cert_to_base64(c) for c in chain_result]
        except Exception as e:
            print(f"Unexpected error during get_full_chain or processing: {str(e)}")
            return jsonify({"status": False, "message": f"Error inesperado al obtener la cadena de certificados: {str(e)}"}), 500

        cuil_t = '0'
        if subject_name:
            try:
                match = re.search(r'SERIALNUMBER=(?:CUIL|CUIT) (\d+)', str(subject_name).upper())
                if not match:
                    match = re.search(r'CN=[^,]*?(?:CUIL|CUIT)[^0-9]*(\d+)', str(subject_name).upper())
                if not match:
                    match = re.search(r'(?:CUIL|CUIT)[^0-9]*(\d+)', str(subject_name).upper())
                cuil_t = match.group(1) if match else '0'
            except Exception as e_cuil:
                print(f"Error extracting CUIL: {e_cuil}")
                cuil_t = '0'

        response_data = {
            "status": True,
            "response": {
                "tokenId": {"id": str(uuid4())},
                "keyId": user_selected_cert.fingerprint(hashes.SHA256()).hex().upper(),
                "certificate": cert_to_base64(user_selected_cert_der),
                "certificateChain": chain_base64,
                "CUIL": cuil_t,
                "encryptionAlgorithm": "RSA"
            },
            "feedback": {
                "info": {
                    "language": "Python", "osName": platform.system(),
                    "osArch": platform.machine(), "osVersion": platform.version(),
                    "arch": platform.architecture()[0], "os": platform.system().upper()
                },
                "TuquitoVersion": "1.8"
            }
        }
        return jsonify(response_data), 200

    except PyKCS11.PyKCS11Error as e:
        print(f"Unhandled PyKCS11Error in /rest/certificates: {str(e)}")
        return jsonify({"status": False, "message": f"Error de PKCS#11: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error in /rest/certificates: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": False, "message": f"Error inesperado en la obtención de certificados: {str(e)}"}), 500
    finally:
        if session:
            try:
                session.logout()
                session.closeSession()
                print("PKCS#11 session logged out and closed in /rest/certificates.")
            except PyKCS11.PyKCS11Error as pkcs_e:
                print(f"Error during PKCS#11 session cleanup in /rest/certificates: {pkcs_e}")

@app.route('/rest/sign', methods=['POST'])
def get_signatures_route():
    global global_pin, global_lib_path
    session = None

    try:
        data = request.get_json()
        if not data or 'dataToSign' not in data:
            return jsonify({"status": False, "message": "No se recibieron datos para firmar."}), 400
        
        data_to_sign_list = data['dataToSign']
        if not data_to_sign_list or not isinstance(data_to_sign_list, list) or not all(isinstance(item, str) for item in data_to_sign_list):
            return jsonify({"status": False, "message": "Formato de datos para firmar incorrecto o lista vacía."}), 400
        
        if not global_lib_path or not global_pin:
            return jsonify({"status": False, "message": "Configuración de token (PIN o librería) no establecida. Por favor, obtenga los certificados primero."}), 400

        try:
            _certificates, session, _subject_name = get_certificates_from_token(global_lib_path, global_pin)
            if not _certificates:
                return jsonify({"status": False, "message": "No se pudo obtener la información del certificado para firmar."}), 404
        except CertTokenLoginError as e:
            print(f"CertTokenLoginError in /rest/sign: {e.message}")
            if hasattr(e, 'error_type') and e.error_type == "BAD_PIN":
                return jsonify({"status": False, "message": "PIN incorrecto."}), 401
            return jsonify({"status": False, "message": e.message, "error_type": e.error_type if hasattr(e, 'error_type') else None}), e.status_code
        except (PKCS11LoadError, CertTokenNotFoundError, CertificateError) as e:
            print(f"Certificate/Token Error in /rest/sign: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code

        try:
            signatures = sign_multiple_data_internal(session, data_to_sign_list)
        except (KeyOrCertificateNotFoundError, PKCS11OperationError, InvalidBase64DataError, SigningError) as e:
            print(f"Signing Error in /rest/sign: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code
        
        response_data = {
            "status": True,
            "response": {"signatures": signatures}
        }
        return jsonify(response_data), 200
    
    except PyKCS11.PyKCS11Error as e:
        print(f"Unhandled PyKCS11Error in /rest/sign: {str(e)}")
        return jsonify({"status": False, "message": f"Error de PKCS#11 al firmar: {str(e)}"}), 500
    except Exception as e:
        print(f"Unexpected error in /rest/sign: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": False, "message": f"Error inesperado al firmar: {str(e)}"}), 500
    finally:
        if session:
            try:
                session.logout()
                session.closeSession()
                print("PKCS#11 session logged out and closed in /rest/sign.")
            except PyKCS11.PyKCS11Error as pkcs_e:
                print(f"Error during PKCS#11 session cleanup in /rest/sign: {pkcs_e}")

@app.route('/test', methods=['GET', 'POST'])
def test_route():
    return jsonify({"status": "success", "message": "Test route"}), 200
    
def is_port_in_use(port):
    for conn in psutil.net_connections():
        if conn.laddr is not None and conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
            return True
    return False

flask_port = 5000

def run_flask_app():
    global port
    port = 5000
    if is_port_in_use(port):
        show_alert(f"El puerto {port} esta en uso. Saliendo de la aplicacion.")
        os._exit(0)
    app.run(host='127.0.0.1', port=port, threaded=True, use_reloader=False)


def on_quit_app(icon):
    print("Saliendo de la aplicación Tuquito...")
    icon.stop()
    os._exit(0)

def setup_tray(icon_obj):
    icon_obj.visible = True

def run_tray_icon():
    global flask_port
    current_file_path = os.path.abspath(__file__)
    icon_filename = 'app_icon_tuquito.png'
    if 'temp' in current_file_path.lower():
        exe_dir = os.path.dirname(current_file_path)
        image_path = os.path.join(exe_dir, 'images', icon_filename)
        if not os.path.exists(image_path):
            image_path = os.path.join(exe_dir, icon_filename)
    else:
        image_path = os.path.join(os.path.dirname(current_file_path), 'images', icon_filename)

    try:
        image = Image.open(image_path)
    except FileNotFoundError:
        print(f"Icono no encontrado en {image_path}. Usando placeholder.")
        image = Image.new('RGB', (64, 64), color = 'red') 

    menu = (MenuItem('Salir de Tuquito', on_quit_app),)
    tray_title = f"Tuquito Autenticador (Puerto: {flask_port})"
    icon = pystray.Icon("tuquito_authenticator", image, tray_title, menu)
    icon.run(setup_tray)

# Helper functions to run Tkinter windows in a dedicated subprocess (avoids Tcl errors in threads)

def _ui_worker(func_name, queue, args):
    """Worker that ejecuta la función gráfica solicitada y devuelve el resultado por Queue."""
    from interfaz import (
        select_token_slot, select_library_file,
        get_pin_from_user, select_certificate
    )
    try:
        if func_name == 'select_token_slot':
            token_info_list, mode = args
            result_container = []
            select_token_slot(token_info_list, result_container, mode)
            queue.put(result_container[0] if result_container else None)
        elif func_name == 'select_certificate':
            certificates, mode = args
            result_container = []
            select_certificate(certificates, result_container, mode)
            queue.put(result_container[0] if result_container else None)
        elif func_name == 'select_library_file':
            queue.put(select_library_file())
        elif func_name == 'get_pin_from_user':
            (mode,) = args
            queue.put(get_pin_from_user(mode))
        else:
            queue.put(None)
    except Exception as e:
        import traceback, sys
        traceback.print_exc()
        queue.put(None)


def run_ui(func_name: str, args: tuple = ()):  # noqa: D401
    """Ejecuta la función gráfica indicada en un proceso separado y devuelve su resultado."""
    q = multiprocessing.Queue()
    p = multiprocessing.Process(target=_ui_worker, args=(func_name, q, args))
    p.start()
    p.join()
    try:
        return q.get_nowait()
    except Exception:
        return None

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask_app, daemon=True)
    flask_thread.start()

    import time
    time.sleep(1) 

    tray_icon_thread = Thread(target=run_tray_icon, daemon=True)
    tray_icon_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Cerrando Tuquito por KeyboardInterrupt...")
        on_quit_app(pystray.Icon("dummy"))