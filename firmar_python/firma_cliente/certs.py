import PyKCS11
import tkinter as tk
from tkinter import Listbox, Scrollbar, Toplevel, Label, filedialog, Frame, PhotoImage
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
from flask_cors import CORS
from threading import Thread
from PIL import Image, ImageTk

app = Flask(__name__)
CORS(app)

# Path to the JSON file that stores token-library correspondences
TOKEN_LIB_FILE = "token_lib.json"

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
        return ''.join(format(x, '02x') for x in token_info["ATR"]), token_info['reader']
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
    global getpin
    getpin = None

    def aceptar():
        global getpin
        getpin = entry_pin.get()
        pinwindow.destroy()

    def cancelar():
        global getpin
        getpin = None
        pinwindow.destroy()

    pinwindow = tk.Tk()

    pinwindow.title("Introduzca su pin")
    pinwindow.geometry(f"500x165")
    pinwindow.resizable(False, False)
    pinwindow.grab_set()

    # Ensure the window opens in the foreground and centered
    pinwindow.attributes('-topmost', True)
    pinwindow.update_idletasks()
    x = (pinwindow.winfo_screenwidth() - pinwindow.winfo_reqwidth()) // 2
    y = (pinwindow.winfo_screenheight() - pinwindow.winfo_reqheight()) // 2
    pinwindow.geometry(f"+{x}+{y}")
    pinwindow.focus_force()


    pin_frame = tk.Frame(pinwindow)
    pin_frame.pack(pady=10)

    # Crear un campo de entrada para el PIN
    label_pin = tk.Label(pin_frame, text="Introduzca su PIN: ", font=("Arial", 14, "bold"))
    label_pin.pack(side="left", pady=10)

    entry_pin = tk.Entry(pin_frame, show="o", width=20, font=("Arial", 14))
    entry_pin.pack(side="left", pady=10)
    entry_pin.focus_set()

    button_frame = Frame(pinwindow)
    button_frame.pack(pady=10)
    style = Style()
    style.configure("TButton", font=("Arial", 12), padding=10)


    original_image = Image.open("./images/aceptar.png")
    resized_image = original_image.resize((25, 25))  # Resize to 50x50 pixels
    iconaceptar = ImageTk.PhotoImage(resized_image)
    original_image = Image.open("./images/cancelar.png")
    resized_image = original_image.resize((25, 25))  # Resize to 50x50 pixels
    iconcancelar = ImageTk.PhotoImage(resized_image)


    # Crear el botón de aceptar
    btn_aceptar = Button(button_frame, text="Aceptar", style="TButton", image=iconaceptar, compound='left', command=aceptar)
    btn_aceptar.pack(side=tk.LEFT, padx=5)

    # Crear el botón de cancelar
    btn_cancelar = Button(button_frame, text="Cancelar", style="TButton", image=iconcancelar, compound='left', command=cancelar)
    btn_cancelar.pack(side=tk.LEFT, padx=5)

    button_frame.pack(pady=10, anchor=tk.CENTER)

    # Ejecutar el bucle principal de la ventana
    pinwindow.mainloop()

    return getpin

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
        index = w.grid_info()['row']
        slot_info = token_info[index]
        slot_label.config(text=f"Slot Seleccionado {index + 1}\nLector: {slot_info['reader']}\nATR: {' '.join(format(x, '02X') for x in slot_info['ATR'])}")
        selected_slot.set(index)
        result.append(index)
        token_window.destroy()


    

    mainwindow = tk.Tk()
    mainwindow.withdraw()  # Hide the mainwindow window

    windows_base_height = 100
    button_height = 65
    total_height = windows_base_height + len(token_info) * button_height
    
    
    token_window = Toplevel(mainwindow)
    token_window.title("Ventana de selección de Token")
    token_window.geometry(f"500x{total_height}")
    token_window.resizable(False, False)
    token_window.grab_set()

    # Ensure the window opens in the foreground and centered
    token_window.attributes('-topmost', True)
    token_window.update_idletasks()
    x = (token_window.winfo_screenwidth() - token_window.winfo_reqwidth()) // 2
    y = (token_window.winfo_screenheight() - token_window.winfo_reqheight()) // 2
    token_window.geometry(f"+{x}+{y}")
    token_window.focus_force()

    # Add instruction label
    instruction_label = Label(token_window, text="Seleccione un Token:", font=("Arial", 18, "bold"))
    instruction_label.pack(pady=10)

    frame = Frame(token_window)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    style = Style()
    style.configure("TButton", font=("Arial", 12), padding=10)

    icon = PhotoImage(file="./images/icono_token.png")

    for i, info in enumerate(token_info):
        button = Button(frame, text=f"   Puerto USB numero: {i + 1}\n   Nombre del Token: {info['reader']}", style="TButton", image=icon, compound='left')
        button.grid(row=i, column=0, columnspan=2, pady=10, padx=30, sticky='ew')
        button.bind("<Button-1>", on_select)


    # Add a single column with weight to center the buttons
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_columnconfigure(1, weight=1)

    slot_label = Label(token_window, text="", justify=tk.LEFT, anchor='w', wraplength=400)
    slot_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=10)

    selected_slot = tk.IntVar(value=-1)
    token_window.wait_window()
    mainwindow.destroy()

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
    cert_window.resizable(False, False)
    cert_window.grab_set()

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

@app.route('/rest/certificates', methods=['GET'])
def get_certificates():
    try:
        token_library_mapping = load_token_library_mapping()
        
        token_info = list_tokens()
        if not token_info:
            return jsonify({"success": False, "message": "No se encontraron tokens."}), 404

        # Slot selection logic
        selected_slot = []
        thread1 = Thread(target=select_token_slot, args=(token_info, selected_slot))
        thread1.start()
        thread1.join()

        if not selected_slot:
            return jsonify({"success": False, "message": "No se seleccionó ningún slot."}), 400

        selected_slot_index = selected_slot[0]
        token_unique_id, token_name = get_token_unique_id(token_info[selected_slot_index])
        if token_name in token_library_mapping:
            lib_path = token_library_mapping[token_name]
        else:
            lib_path = select_library_file()
            if not lib_path:
                return jsonify({"success": False, "message": "No se seleccionó ninguna biblioteca."}), 400
            token_library_mapping[token_name] = lib_path

            save_token_library_mapping(token_library_mapping)
        pin = get_pin_from_user()
        if not pin:
            return jsonify({"success": False, "message": "Entrada de PIN cancelada."}), 400

        certificates = get_certificates_from_token(lib_path, pin, selected_slot_index)
        if not certificates:
            return jsonify({"success": False, "message": "No se encontraron certificados en el token."}), 404

        # Certificate selection logic
        selected_cert = []
        thread2 = Thread(target=select_certificate, args=(certificates, selected_cert))
        thread2.start()
        thread2.join()

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

if __name__ == "__main__":
    app.run(host='127.0.0.1', port=9795)

