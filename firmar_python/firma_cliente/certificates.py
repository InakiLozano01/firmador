##################################################
###              Imports externos              ###
##################################################

import base64
import requests
import PyKCS11
import tkinter as tk
from tkinter import Toplevel, Label, Button, Listbox, Scrollbar
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
                response = requests.get(issuer_url)
                try:
                    return x509.load_der_x509_certificate(response.content), 200
                except ValueError:
                    print("Error al parsear formato DER, intentando PEM...")
                    return x509.load_pem_x509_certificate(response.content), 200
    except x509.ExtensionNotFound:
        return jsonify({"status": "error", "message": "No se encontró la extensión de Información de Acceso a la Autoridad."}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al obtener el certificado del emisor: {str(e)}"}), 500

def get_certificates_from_token(lib_path, pin, slot_index):
    pkcs11 = PyKCS11.PyKCS11Lib()
    try:
        pkcs11.load(lib_path)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al cargar la biblioteca PKCS#11: {str(e)}"}), 500

    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        return jsonify({"status": "error", "message": "No se encontraron tokens."}), 404

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
            return jsonify({"status": "error", "message": "Error al obtener el certificado del emisor."}), 500
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