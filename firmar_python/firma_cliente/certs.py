import PyKCS11
import tkinter as tk
from tkinter import simpledialog, messagebox, Listbox, Scrollbar, Toplevel, Label, filedialog
from tkinter.ttk import Button, Style
from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
import requests
import base64
import json
import uuid
import platform
import os
from smartcard.System import readers
from smartcard.Exceptions import NoCardException
from flask import Flask, jsonify, request
from threading import Thread
import subprocess
import atexit
from PyPDF2 import PdfFileReader
import io
from flask_cors import CORS


app = Flask(__name__)
CORS(app)

# Path to the JSON file that stores token-library correspondences
TOKEN_LIB_FILE = "token_lib.json"

java_process = None
java_process_started = False

def load_token_library_mapping():
    try:
        if os.path.exists(TOKEN_LIB_FILE):
            with open(TOKEN_LIB_FILE, 'r') as file:
                return json.load(file)
        return {}
    except (json.JSONDecodeError, ValueError):
        return {}

def save_token_library_mapping(mapping):
    try:
        with open(TOKEN_LIB_FILE, 'w') as file:
            json.dump(mapping, file)
    except Exception as e:
        print(f"Error saving token library mapping: {str(e)}")

def get_token_unique_id(token_info):
    try:
        return ''.join(format(x, '02x') for x in token_info["ATR"])
    except Exception as e:
        print(f"Error getting token unique ID: {str(e)}")
        return None

def select_library_file():
    try:
        return filedialog.askopenfilename(initialdir="C:\\Windows\\System32\\", title="Seleccione la biblioteca DLL", filetypes=[("DLL files", "*.dll")])
    except Exception as e:
        print(f"Error selecting library file: {str(e)}")
        return None

def get_pin_from_user():
    try:
        root = tk.Tk()
        root.withdraw()
        pin = simpledialog.askstring("PIN del Token", "Ingrese el PIN para el token:", show='*')
        root.destroy()
        return pin
    except Exception as e:
        print(f"Error getting PIN from user: {str(e)}")
        return None

def get_issuer_cert(cert):
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        for access_description in aia:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_url = access_description.access_location.value
                print(f"Obteniendo certificado del emisor desde: {issuer_url}")
                response = requests.get(issuer_url)
                try:
                    return x509.load_der_x509_certificate(response.content)
                except ValueError:
                    print("Error al parsear formato DER, intentando PEM...")
                    return x509.load_pem_x509_certificate(response.content)
    except x509.ExtensionNotFound:
        print("No se encontró la extensión de Información de Acceso a la Autoridad.")
    except Exception as e:
        print(f"Error al obtener el certificado del emisor: {str(e)}")
    return None

def get_certificates_from_token(lib_path, pin, slot_index):
    pkcs11 = PyKCS11.PyKCS11Lib()
    try:
        pkcs11.load(lib_path)
    except Exception as e:
        print(f"Error al cargar la biblioteca PKCS#11: {str(e)}")
        return None, None

    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        print("No se encontró el token")
        return None, None

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

    session.logout()
    session.closeSession()
    return certificates

def get_full_chain(cert, cert_der):
    chain = [cert_der]
    current_cert = cert
    while True:
        if current_cert.issuer == current_cert.subject:
            print("Certificado autofirmado alcanzado. Construcción de cadena completada.")
            break
        issuer_cert = get_issuer_cert(current_cert)
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
    return base64.b64encode(cert_der).decode('ascii')

def list_smartcard_readers():
    try:
        r = readers()
        return r
    except Exception as e:
        print(f"Error listing smart card readers: {str(e)}")
        return []

def list_tokens():
    token_info = []
    reader_list = list_smartcard_readers()
    for reader in reader_list:
        try:
            connection = reader.createConnection()
            connection.connect()
            atr = connection.getATR()
            token_info.append({"reader": reader.name, "ATR": atr})
        except NoCardException:
            pass
        except Exception as e:
            print(f"Error accessing reader {reader}: {str(e)}")
    return token_info

def select_token_slot(token_info, result):
    def on_select(evt):
        w = evt.widget
        index = int(w.curselection()[0])
        slot_info = token_info[index]
        slot_label.config(text=f"Slot Seleccionado {index + 1}\nLector: {slot_info['reader']}\nATR: {' '.join(format(x, '02X') for x in slot_info['ATR'])}")
        selected_slot.set(index)
        result.append(index)
        token_window.destroy()

    root = tk.Tk()
    root.withdraw()  # Hide the root window

    token_window = Toplevel(root)
    token_window.title("Seleccionar un Slot de Token")
    token_window.geometry("500x400")
    token_window.resizable(True, True)  # Allow resizing

    # Ensure the window opens in the foreground and centered
    token_window.attributes('-topmost', True)
    token_window.update_idletasks()
    x = (token_window.winfo_screenwidth() - token_window.winfo_reqwidth()) // 2
    y = (token_window.winfo_screenheight() - token_window.winfo_reqheight()) // 2
    token_window.geometry(f"+{x}+{y}")
    token_window.focus_force()

    # Add instruction label
    instruction_label = Label(token_window, text="Seleccione un Slot de Token:", font=("Arial", 12))
    instruction_label.pack(pady=10)

    scrollbar = Scrollbar(token_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = Listbox(token_window, yscrollcommand=scrollbar.set, width=100, height=15)
    for i, info in enumerate(token_info):
        listbox.insert(tk.END, f"Slot {i + 1}: Lector: {info['reader']}")
    listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    listbox.bind('<<ListboxSelect>>', on_select)
    scrollbar.config(command=listbox.yview)

    slot_label = Label(token_window, text="", justify=tk.LEFT, anchor='w', wraplength=400)
    slot_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=10)

    selected_slot = tk.IntVar(value=-1)
    select_button = Button(token_window, text="Seleccionar Slot", command=token_window.destroy)
    select_button.pack(pady=10)
    token_window.wait_window()
    root.destroy()

def select_certificate(certificates, result):
    def on_select(evt):
        w = evt.widget
        index = int(w.curselection()[0])
        cert_info = certificates[index]
        result.append(index)
        cert_window.destroy()

    root = tk.Tk()
    root.withdraw()  # Hide the root window

    cert_window = Toplevel(root)
    cert_window.title("Seleccionar un Certificado")
    cert_window.geometry("600x500")
    cert_window.resizable(True, True)  # Allow resizing

    # Ensure the window opens in the foreground and centered
    cert_window.attributes('-topmost', True)
    cert_window.update_idletasks()
    x = (cert_window.winfo_screenwidth() - cert_window.winfo_reqwidth()) // 2
    y = (cert_window.winfo_screenheight() - cert_window.winfo_reqheight()) // 2
    cert_window.geometry(f"+{x}+{y}")
    cert_window.focus_force()

    # Add instruction label
    instruction_label = Label(cert_window, text="Seleccione un Certificado:", font=("Arial", 12))
    instruction_label.pack(pady=10)

    scrollbar = Scrollbar(cert_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = Listbox(cert_window, yscrollcommand=scrollbar.set, width=100, height=20)
    for i, (cert, _) in enumerate(certificates):
        listbox.insert(tk.END, f"Certificado {i + 1}: {cert.subject}")
    listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    listbox.bind('<<ListboxSelect>>', on_select)
    scrollbar.config(command=listbox.yview)

    cert_label = Label(cert_window, text="", justify=tk.LEFT, anchor='w', wraplength=500)
    cert_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=10)

    selected_cert = tk.IntVar(value=-1)
    select_button = Button(cert_window, text="Seleccionar Certificado", command=cert_window.destroy)
    select_button.pack(pady=10)
    cert_window.wait_window()
    root.destroy()

@app.before_request
def start_java_process():
    global java_process_started
    global java_process

    if not java_process_started:
        print("Starting Java process...")
        java_process = subprocess.Popen(['java', '-jar', r'C:\Users\kakit\OneDrive\Downloads\Projects\Firmador\firmar_python\firma_cliente\dssapp\dss-demo-webapp\target\dss-signature-rest-6.1.RC1.jar'])
        java_process_started = True

        # Ensure Java process is terminated when Flask app shuts down
        def cleanup():
            java_process.terminate()

        atexit.register(cleanup)

@app.route('/rest/certificates', methods=['GET'])
def get_certificates():
    try:
        token_library_mapping = load_token_library_mapping()
        
        token_info = list_tokens()
        if not token_info:
            return jsonify({"success": False, "message": "No se encontraron tokens."}), 404

        # Slot selection logic
        selected_slot = []
        thread = Thread(target=select_token_slot, args=(token_info, selected_slot))
        thread.start()
        thread.join()

        if not selected_slot:
            return jsonify({"success": False, "message": "No se seleccionó ningún slot."}), 400

        selected_slot_index = selected_slot[0]
        token_unique_id = get_token_unique_id(token_info[selected_slot_index])
        if token_unique_id in token_library_mapping:
            lib_path = token_library_mapping[token_unique_id]
        else:
            lib_path = select_library_file()
            if not lib_path:
                return jsonify({"success": False, "message": "No se seleccionó ninguna biblioteca."}), 400
            token_library_mapping[token_unique_id] = lib_path
            save_token_library_mapping(token_library_mapping)

        pin = get_pin_from_user()
        if not pin:
            return jsonify({"success": False, "message": "Entrada de PIN cancelada."}), 400

        certificates = get_certificates_from_token(lib_path, pin, selected_slot_index)
        if not certificates:
            return jsonify({"success": False, "message": "No se encontraron certificados en el token."}), 404

        # Certificate selection logic
        selected_cert = []
        thread = Thread(target=select_certificate, args=(certificates, selected_cert))
        thread.start()
        thread.join()

        if not selected_cert:
            return jsonify({"success": False, "message": "No se seleccionó ningún certificado."}), 400

        selected_index = selected_cert[0]
        cert, cert_der = certificates[selected_index]
        cert_chain = get_full_chain(cert, cert_der)
        chain_base64 = [cert_to_base64(c) for c in cert_chain]

        response = {
            "success": True,
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
                    "jreVendor": "ORACLE",
                    "osName": platform.system(),
                    "osArch": platform.machine(),
                    "osVersion": platform.version(),
                    "arch": platform.architecture()[0],
                    "os": platform.system().upper()
                },
                "nexuVersion": "1.22"
            }
        }

        responsejson = json.loads(json.dumps(response))

        return jsonify(responsejson), 200
    except PyKCS11.PyKCS11Error as e:
        return jsonify({"success": False, "message": f"Error de PyKCS11: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"Error inesperado en get_certificates: {str(e)}"}), 500

def digestpdf(pdf, certificates, stamp, field_id, encoded_image, current_time):
    body = {
            "parameters": {
                "signingCertificate": {
                    "encodedCertificate": certificates['certificate']
                },
                "certificateChain": [
                    {"encodedCertificate": cert} for cert in certificates['certificateChain']
                ],
                "detachedContents": None,
                "asicContainerType": None,
                "signatureLevel": "PAdES_BASELINE_B",
                "signaturePackaging": "ENVELOPED",
                "embedXML": False,
                "manifestSignature": False,
                "jwsSerializationType": None,
                "sigDMechanism": None,
                "signatureAlgorithm": "RSA_SHA256",
                "digestAlgorithm": "SHA256",
                "encryptionAlgorithm": "RSA",
                "referenceDigestAlgorithm": None,
                "maskGenerationFunction": None,
                "contentTimestamps": None,
                "contentTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signatureTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "archiveTimestampParameters": {
                    "digestAlgorithm": "SHA256",
                    "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
                    "timestampContainerForm": None
                },
                "signWithExpiredCertificate": False,
                "generateTBSWithoutCertificate": False,
                "imageParameters": {
                    "alignmentHorizontal": None,
                    "alignmentVertical": None,
                    "imageScaling": "ZOOM_AND_CENTER",
                    "backgroundColor": None,
                    "dpi": 200,
                    "image": {
                        "bytes": encoded_image,
                        "name": "image.png"
                    },
                    "fieldParameters": {
                        "fieldId": f"{field_id}",
                        "originX": 0,
                        "originY": 0,
                        "width": None,
                        "height": None,
                        "rotation": None,
                        "page": len(PdfFileReader(io.BytesIO(base64.b64decode(pdf))).pages)
                    },
                    "textParameters": None,
                    "zoom": None
                },
                "signatureIdToCounterSign": None,
                "blevelParams": {
                    "trustAnchorBPPolicy": True,
                    "signingDate": current_time,  # Current time in milliseconds
                    "claimedSignerRoles": [f"{stamp}"],
                    "policyId": None,
                    "policyQualifier": None,
                    "policyDescription": None,
                    "policyDigestAlgorithm": None,
                    "policyDigestValue": None,
                    "policySpuri": None,
                    "commitmentTypeIndications": None,
                    "signerLocationPostalAddress": [
                        "Congreso 180",
                        "4000 San Miguel de Tucumán",
                        "Tucumán",
                        "AR"
                    ],
                    "signerLocationPostalCode": "4000",
                    "signerLocationLocality": "San Miguel de Tucumán",
                    "signerLocationStateOrProvince": "Tucumán",
                    "signerLocationCountry": "AR",
                    "signerLocationStreet": "Congreso 180"
                }
            },
            "toSignDocument": {
                "bytes": pdf,
                "digestAlgorithm": None,
                "name": "document.pdf"
            }
        }
    response = requests.post('http://localhost:8080/services/rest/getDataToSign', json=body)
    return response

if __name__ == "__main__":
    java_process = subprocess.Popen(['java', '-jar', r'C:\Users\kakit\OneDrive\Downloads\Projects\Firmador\firmar_python\firma_cliente\dssapp\dss-demo-webapp\target\dss-signature-rest-6.1.RC1.jar'])
    java_process_started = True

    def cleanup():
        java_process.terminate()

    atexit.register(cleanup)

    app.run(host='127.0.0.1', port=9795)
