##################################################
###              Imports externos              ###
##################################################

import sys

# Frozen helper processes must branch before importing Flask, PyKCS11, Pillow,
# or tray dependencies. This keeps each dialog startup lightweight.
if len(sys.argv) >= 2 and sys.argv[1] == "--ui-helper":
    sys.argv[:] = ["ui_helper", *sys.argv[2:]]
    from ui_helper.__main__ import main as _ui_main

    _ui_main()
    sys.exit(0)

if len(sys.argv) >= 2 and sys.argv[1] == "--pkcs11-worker":
    from pkcs11_worker import serve_worker

    serve_worker()
    sys.exit(0)

from base64 import b64decode
import platform
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from flask import Flask, g, jsonify, request
from threading import Lock, Thread
from flask_cors import CORS
from werkzeug.serving import make_server
import os
import pystray
from pystray import MenuItem
from PIL import Image
import re
import time
from ui_bridge import run_ui as _run_ui_bridge  # Subprocess-based UI bridge

##################################################
###              Imports propios               ###
##################################################

from tokenmg import (
    load_token_library_mapping, save_token_library_mapping,
    list_tokens_internal, get_token_unique_id_internal,
    is_token_library_path_usable,
    TokenManagementError, TokenMappingError, SmartcardReaderError,
    NoSmartcardFoundError, TokenATRReadError, TokenIdError
)
from certificates import (
    get_full_chain, cert_to_base64,
    CertificateError, AIAExtensionNotFoundError, IssuerCertificateFetchError,
    CertificateParsingError,
)
from interfaz import show_alert
from diagnostics import (
    close_diagnostics,
    configure_diagnostics,
    log_event,
)
from pkcs11_worker import (
    PKCS11WorkerClient,
    PKCS11WorkerError,
    WorkerTimeoutError,
)
from signing_transaction import (
    SigningTransactionError,
    SigningTransactionManager,
)

##################################################
###      Configuracion de aplicacion Flask     ###
##################################################

app = Flask(__name__)
CORS(app)

##################################################
###                 Endpoints                  ###
##################################################

SIGNING_TRANSACTION_TTL_SECONDS = float(
    os.environ.get("TUQUITO_SIGNING_TRANSACTION_TTL_SECONDS", "300")
)
PKCS11_COMMAND_TIMEOUT_SECONDS = float(
    os.environ.get("TUQUITO_PKCS11_COMMAND_TIMEOUT_SECONDS", "30")
)
CERT_CHAIN_TIMEOUT_SECONDS = float(
    os.environ.get("TUQUITO_CERT_CHAIN_TIMEOUT_SECONDS", "20")
)
MAX_SIGNING_ITEMS = int(
    os.environ.get("TUQUITO_MAX_SIGNING_ITEMS", "1000")
)
MAX_SIGNING_ITEM_CHARS = int(
    os.environ.get("TUQUITO_MAX_SIGNING_ITEM_CHARS", "1000000")
)
MAX_REQUEST_BYTES = int(
    os.environ.get("TUQUITO_MAX_REQUEST_BYTES", str(16 * 1024 * 1024))
)
app.config["MAX_CONTENT_LENGTH"] = MAX_REQUEST_BYTES
transaction_manager = SigningTransactionManager(
    ttl_seconds=SIGNING_TRANSACTION_TTL_SECONDS
)
certificate_flow_lock = Lock()


def _request_origin() -> str | None:
    origin = request.headers.get("Origin")
    return origin.strip() if origin and origin.strip() else None


def _normalize_token_id(value):
    if isinstance(value, dict):
        value = value.get("id")
    return value if isinstance(value, str) and value else None


def _start_phase(phase: str) -> float:
    log_event("phase_started", phase=phase)
    return time.monotonic()


def _finish_phase(phase: str, started_at: float, **fields) -> None:
    log_event(
        "phase_completed",
        phase=phase,
        duration_ms=round((time.monotonic() - started_at) * 1000, 1),
        **fields,
    )


@app.before_request
def _record_request_start():
    g.request_started_at = time.monotonic()


@app.after_request
def _record_request_end(response):
    started_at = getattr(g, "request_started_at", time.monotonic())
    log_event(
        "http_request_completed",
        route=request.path,
        method=request.method,
        status_code=response.status_code,
        duration_ms=round((time.monotonic() - started_at) * 1000, 1),
        origin_present=bool(_request_origin()),
    )
    return response


@app.route('/rest/certificates', methods=['GET'])
def get_certificates_route():
    if not certificate_flow_lock.acquire(blocking=False):
        return jsonify({
            "status": False,
            "message": "Ya hay una selección de certificado en curso.",
        }), 409
    worker = None
    try:
        caller_origin = _request_origin()
        active_response = transaction_manager.get_active_certificate_response(
            caller_origin
        )
        if active_response is not None:
            log_event(
                "certificate_request_reused",
                origin_present=bool(caller_origin),
            )
            return jsonify(active_response), 200
        if transaction_manager.has_active_transaction():
            return jsonify({
                "status": False,
                "message": "Ya hay una transacción de firma pendiente.",
            }), 409
        mode = 'exe' if getattr(sys, "frozen", False) else 'python'

        print(f"Mode: {mode}")

        try:
            token_library_mapping = load_token_library_mapping()
            print(f"Token library mapping: {token_library_mapping}")
        except TokenMappingError as e:
            print(f"TokenMappingError in load_token_library_mapping: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code

        try:
            phase_started = _start_phase("token_enumeration")
            token_info_list = list_tokens_internal()
            _finish_phase(
                "token_enumeration",
                phase_started,
                token_count=len(token_info_list),
            )
            if not token_info_list:
                return jsonify({"status": False, "message": "No se encontraron tokens o tarjetas en los lectores."}), 404
        except NoSmartcardFoundError as e:
            print(f"NoSmartcardFoundError in list_tokens_internal: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code
        except SmartcardReaderError as e:
            print(f"SmartcardReaderError in list_tokens_internal: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code

        # -------------------- SELECCIÓN DE TOKEN --------------------
        phase_started = _start_phase("token_selection_ui")
        selected_slot_index = run_ui('select_token_slot', (token_info_list, mode))
        _finish_phase("token_selection_ui", phase_started)
        print(f"Selected slot index: {selected_slot_index}")

        if selected_slot_index is None:
            return jsonify({"status": False, "message": "No se seleccionó ningún slot de token."}), 400
        if not isinstance(selected_slot_index, int) or not 0 <= selected_slot_index < len(token_info_list):
            return jsonify({"status": False, "message": "Selección de token inválida."}), 400

        selected_token_info = token_info_list[selected_slot_index]
        print(f"Selected token info: {selected_token_info}")

        try:
            token_atr_hex, token_name = get_token_unique_id_internal(selected_token_info)
        except TokenIdError as e:
            print(f"TokenIdError in get_token_unique_id_internal: {e.message}")
            return jsonify({"status": False, "message": e.message}), e.status_code

        mapping_key = token_atr_hex.upper()
        lib_path = None
        if mapping_key in token_library_mapping:
            lib_path = token_library_mapping[mapping_key]
        elif token_name in token_library_mapping:
            # Backward-compatible read of existing reader-name mappings.
            lib_path = token_library_mapping[token_name]

        if lib_path and not is_token_library_path_usable(lib_path):
            token_library_mapping.pop(mapping_key, None)
            token_library_mapping.pop(token_name, None)
            lib_path = None

        if lib_path is None:
            chosen_lib_path = run_ui('select_library_file')
            if not chosen_lib_path:
                return jsonify({"status": False, "message": "No se seleccionó ninguna biblioteca de token o se canceló la selección."}), 400
            if not is_token_library_path_usable(chosen_lib_path):
                return jsonify({
                    "status": False,
                    "message": "La biblioteca PKCS#11 seleccionada no existe o no es válida.",
                }), 400
            lib_path = chosen_lib_path
            token_library_mapping[mapping_key] = lib_path
            token_library_mapping.pop(token_name, None)
            try:
                save_token_library_mapping(token_library_mapping)
            except TokenMappingError as e:
                print(f"TokenMappingError in save_token_library_mapping: {e.message}")
                return jsonify({"status": False, "message": e.message}), e.status_code

        phase_started = _start_phase("pin_entry_ui")
        pin_input = run_ui('get_pin_from_user', (mode, caller_origin))
        _finish_phase("pin_entry_ui", phase_started)
        if not pin_input: # Handles both cancellation and dialog setup errors from get_pin_from_user
            return jsonify({"status": False, "message": "Entrada de PIN cancelada o fallida."}), 400

        try:
            phase_started = _start_phase("pkcs11_worker_open")
            worker = PKCS11WorkerClient.start(
                lib_path,
                pin_input,
                selected_token_info["reader"],
                command_timeout=PKCS11_COMMAND_TIMEOUT_SECONDS,
            )
            _finish_phase(
                "pkcs11_worker_open",
                phase_started,
                certificate_count=len(worker.certificates),
            )
        except PKCS11WorkerError as e:
            print(f"PKCS11WorkerError: {e}")
            if e.error_type == "BAD_PIN":
                return jsonify({"status": False, "message": "PIN incorrecto."}), 401
            if e.error_type == "PIN_LOCKED":
                return jsonify({"status": False, "message": "PIN bloqueado."}), 423
            status_code = 504 if isinstance(e, WorkerTimeoutError) else 500
            return jsonify({"status": False, "message": str(e)}), status_code

        certificates = []
        for certificate_info in worker.certificates:
            cert_der = b64decode(certificate_info["certificate"], validate=True)
            cert = x509.load_der_x509_certificate(cert_der)
            certificates.append((cert, cert_der))

        if not certificates:
            return jsonify({"status": False, "message": "No se encontraron certificados en el token."}), 404

        serializable_certs_info = [
            certificate_info["subject"]
            for certificate_info in worker.certificates
        ]

        phase_started = _start_phase("certificate_selection_ui")
        selected_index = run_ui('select_certificate', (serializable_certs_info, mode))
        _finish_phase("certificate_selection_ui", phase_started)

        if selected_index is None:
            return jsonify({"status": False, "message": "No se seleccionó ningún certificado."}), 400
        if not isinstance(selected_index, int) or not 0 <= selected_index < len(certificates):
            return jsonify({"status": False, "message": "Selección de certificado inválida."}), 400

        worker.select_certificate(selected_index)
        user_selected_cert, user_selected_cert_der = certificates[selected_index]

        try:
            phase_started = _start_phase("certificate_chain")
            chain_result, chain_status_code = get_full_chain(
                user_selected_cert,
                user_selected_cert_der,
                token_atr_hex,
                max_duration_seconds=CERT_CHAIN_TIMEOUT_SECONDS,
            )
            _finish_phase(
                "certificate_chain",
                phase_started,
                chain_status_code=chain_status_code,
            )
            if chain_status_code != 200:
                print(f"Error from get_full_chain (status {chain_status_code})")
                return chain_result, chain_status_code
            chain_base64 = [cert_to_base64(c) for c in chain_result]
        except Exception as e:
            print(f"Unexpected error during get_full_chain or processing: {str(e)}")
            return jsonify({"status": False, "message": f"Error inesperado al obtener la cadena de certificados: {str(e)}"}), 500

        cuil_t = '0'
        if user_selected_cert.subject:
            try:
                selected_subject = user_selected_cert.subject.rfc4514_string()
                match = re.search(r'SERIALNUMBER=(?:CUIL|CUIT) (\d+)', selected_subject.upper())
                if not match:
                    match = re.search(r'CN=[^,]*?(?:CUIL|CUIT)[^0-9]*(\d+)', selected_subject.upper())
                if not match:
                    match = re.search(r'(?:CUIL|CUIT)[^0-9]*(\d+)', selected_subject.upper())
                cuil_t = match.group(1) if match else '0'
            except Exception as e_cuil:
                print(f"Error extracting CUIL: {e_cuil}")
                cuil_t = '0'

        key_id = user_selected_cert.fingerprint(hashes.SHA256()).hex().upper()
        token_id = transaction_manager.create(
            worker=worker,
            origin=caller_origin,
            key_id=key_id,
        )
        worker = None
        response_data = {
            "status": True,
            "response": {
                "tokenId": {"id": token_id},
                "keyId": key_id,
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
                "TuquitoVersion": "2.4"
            }
        }
        transaction_manager.cache_certificate_response(token_id, response_data)
        return jsonify(response_data), 200

    except SigningTransactionError as e:
        return jsonify({"status": False, "message": str(e)}), e.status_code
    except Exception as e:
        print(f"Unexpected error in /rest/certificates: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": False, "message": f"Error inesperado en la obtención de certificados: {str(e)}"}), 500
    finally:
        if worker is not None:
            worker.close()
        certificate_flow_lock.release()

@app.route('/rest/sign', methods=['POST'])
def get_signatures_route():
    try:
        data = request.get_json()
        if not data or 'dataToSign' not in data:
            return jsonify({"status": False, "message": "No se recibieron datos para firmar."}), 400

        data_to_sign_list = data['dataToSign']
        if not data_to_sign_list or not isinstance(data_to_sign_list, list) or not all(isinstance(item, str) for item in data_to_sign_list):
            return jsonify({"status": False, "message": "Formato de datos para firmar incorrecto o lista vacía."}), 400
        if len(data_to_sign_list) > MAX_SIGNING_ITEMS:
            return jsonify({
                "status": False,
                "message": "La cantidad de elementos a firmar supera el límite permitido.",
            }), 413
        if any(len(item) > MAX_SIGNING_ITEM_CHARS for item in data_to_sign_list):
            return jsonify({
                "status": False,
                "message": "Un elemento a firmar supera el tamaño permitido.",
            }), 413

        token_id = _normalize_token_id(data.get("tokenId"))
        key_id = data.get("keyId")
        if not token_id or not isinstance(key_id, str) or not key_id:
            return jsonify({
                "status": False,
                "message": "tokenId y keyId son obligatorios para firmar.",
            }), 400

        phase_started = _start_phase("pkcs11_batch_sign")
        signatures = transaction_manager.consume(
            token_id=token_id,
            key_id=key_id,
            origin=_request_origin(),
            data_to_sign=data_to_sign_list,
        )
        _finish_phase(
            "pkcs11_batch_sign",
            phase_started,
            item_count=len(data_to_sign_list),
        )

        response_data = {
            "status": True,
            "response": {"signatures": signatures}
        }
        return jsonify(response_data), 200

    except SigningTransactionError as e:
        return jsonify({"status": False, "message": str(e)}), e.status_code
    except PKCS11WorkerError as e:
        status_code = 504 if isinstance(e, WorkerTimeoutError) else 500
        return jsonify({"status": False, "message": str(e)}), status_code
    except Exception as e:
        print(f"Unexpected error in /rest/sign: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"status": False, "message": f"Error inesperado al firmar: {str(e)}"}), 500

@app.route('/test', methods=['GET', 'POST'])
def test_route():
    return jsonify({"status": "success", "message": "Test route"}), 200


flask_port = 5000
flask_server = None


class SignerStartupError(Exception):
    pass


def create_flask_server(server_factory=make_server):
    """Bind the port synchronously so startup cannot silently fail in a thread."""
    try:
        return server_factory(
            '127.0.0.1',
            flask_port,
            app,
            threaded=True,
        )
    except (OSError, SystemExit) as exc:
        raise SignerStartupError(
            f"No se pudo iniciar Tuquito en el puerto {flask_port}: {exc}"
        ) from exc


def on_quit_app(icon):
    global flask_server
    print("Saliendo de la aplicación Tuquito...")
    transaction_manager.discard_all()
    if flask_server is not None:
        flask_server.shutdown()
        flask_server = None
    close_diagnostics()
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
    tray_title = f"Tuquito (Puerto: {flask_port})"
    icon = pystray.Icon("tuquito_authenticator", image, tray_title, menu)
    icon.run(setup_tray)

# Wrapper that keeps the original signature (func_name, args_tuple)
# so existing endpoint code does not need to change.

def run_ui(func_name: str, args: tuple = ()):  # noqa: D401
    """Delegate to ui_bridge.run_ui while accepting a *single* tuple like before."""

    if args is None:
        args = ()
    if not isinstance(args, tuple):
        # For safety convert single parameter to tuple
        args = (args,)
    return _run_ui_bridge(func_name, *args)

if __name__ == "__main__":
    diagnostics_log_path = configure_diagnostics()
    log_event(
        "application_starting",
        port=flask_port,
        diagnostics_log_path=diagnostics_log_path,
    )
    try:
        flask_server = create_flask_server()
    except SignerStartupError as exc:
        log_event("application_start_failed", error_type=type(exc).__name__)
        show_alert(str(exc))
        close_diagnostics()
        sys.exit(1)

    flask_thread = Thread(target=flask_server.serve_forever, daemon=True)
    flask_thread.start()
    log_event(
        "application_listening",
        host="127.0.0.1",
        port=flask_port,
    )

    tray_icon_thread = Thread(target=run_tray_icon, daemon=True)
    tray_icon_thread.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Cerrando Tuquito por KeyboardInterrupt...")
        on_quit_app(pystray.Icon("dummy"))