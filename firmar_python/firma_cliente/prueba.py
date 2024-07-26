import PyKCS11
import tkinter as tk
from tkinter import simpledialog, messagebox, Listbox, Scrollbar, Toplevel
from tkinter.ttk import Button, Style
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
import requests
import base64
import wincertstore
import ssl
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes

def get_pin_from_user():
    root = tk.Tk()
    root.withdraw()
    pin = simpledialog.askstring("Token PIN", "Enter PIN for the token:", show='*')
    root.destroy()
    return pin

def get_issuer_cert(cert):
    try:
        aia = cert.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_INFORMATION_ACCESS).value
        for access_description in aia:
            if access_description.access_method == AuthorityInformationAccessOID.CA_ISSUERS:
                issuer_url = access_description.access_location.value
                print(f"Fetching issuer certificate from: {issuer_url}")
                response = requests.get(issuer_url)
                try:
                    return x509.load_der_x509_certificate(response.content)
                except ValueError:
                    print("Failed to parse DER format, trying PEM...")
                    return x509.load_pem_x509_certificate(response.content)
    except x509.ExtensionNotFound:
        print("No Authority Information Access extension found.")
    except Exception as e:
        print(f"Error fetching issuer certificate: {str(e)}")
    return None

def get_certificate_from_token(lib_path, pin, slot_index):
    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load(lib_path)
    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        print("No token found")
        return None

    session = pkcs11.openSession(slots[slot_index], PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
    session.login(pin)

    cert_attributes = [PyKCS11.CKA_CLASS, PyKCS11.CKA_CERTIFICATE_TYPE, PyKCS11.CKA_VALUE]

    for obj in session.findObjects():
        attributes = session.getAttributeValue(obj, cert_attributes)
        if attributes[0] == PyKCS11.CKO_CERTIFICATE:
            cert_der = bytes(attributes[2])
            cert = x509.load_der_x509_certificate(cert_der)
            print(f"Found certificate on token: {cert.subject}")
            session.logout()
            session.closeSession()
            return cert, cert_der

    session.logout()
    session.closeSession()
    return None, None

def list_tokens(lib_path):
    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load(lib_path)
    slots = pkcs11.getSlotList(tokenPresent=True)
    token_info = []
    for slot in slots:
        info = pkcs11.getTokenInfo(slot)
        token_info.append(info)
    return token_info

def get_certificates_from_windows_store():
    certificates = []
    if os.name == 'nt':
        for storename in ("ROOT", "CA", "MY"):
            with wincertstore.CertSystemStore(storename) as store:
                for cert in store.itercerts(usage=wincertstore.SERVER_AUTH):
                    pem = cert.get_pem()
                    encoded_der = ''.join(pem.split("\n")[1:-2])
                    cert_bytes = base64.b64decode(encoded_der)
                    cert_pem = ssl.DER_cert_to_PEM_cert(cert_bytes)
                    cert_details = x509.load_pem_x509_certificate(cert_pem.encode('utf-8'), default_backend())
                    certificates.append(cert_details)
    return certificates

def display_certificate_info(cert):
    info = f"Subject: {cert.subject}\nIssuer: {cert.issuer}\nNot valid before: {cert.not_valid_before}\nNot valid after: {cert.not_valid_after}\n"
    return info

def cert_to_base64(cert_der):
    return base64.b64encode(cert_der).decode('ascii')

def show_certificates(certificates):
    def on_select(evt):
        w = evt.widget
        index = int(w.curselection()[0])
        cert = certificates[index]
        cert_info = display_certificate_info(cert)
        info_label.config(text=cert_info)

    cert_window = Toplevel(root)
    cert_window.title("Select a Certificate")
    scrollbar = Scrollbar(cert_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox = Listbox(cert_window, yscrollcommand=scrollbar.set, width=100)
    for i, cert in enumerate(certificates):
        listbox.insert(tk.END, f"Certificate {i + 1}: {cert.subject}")
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox.bind('<<ListboxSelect>>', on_select)
    scrollbar.config(command=listbox.yview)
    info_label = tk.Label(cert_window, text="", justify=tk.LEFT, anchor='w')
    info_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
    cert_window.mainloop()

def select_token_slot(token_info):
    def on_select(evt):
        w = evt.widget
        index = int(w.curselection()[0])
        slot_info = token_info[index]
        slot_label.config(text=f"Selected Slot {index + 1}\nLabel: {slot_info.label}\nModel: {slot_info.model}\nManufacturer: {slot_info.manufacturerID}\nSerial: {slot_info.serialNumber}")
        selected_slot.set(index)

    token_window = Toplevel(root)
    token_window.title("Select a Token Slot")
    scrollbar = Scrollbar(token_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
    listbox = Listbox(token_window, yscrollcommand=scrollbar.set, width=100)
    for i, info in enumerate(token_info):
        listbox.insert(tk.END, f"Slot {i + 1}: Label: {info.label}, Model: {info.model}")
    listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    listbox.bind('<<ListboxSelect>>', on_select)
    scrollbar.config(command=listbox.yview)
    slot_label = tk.Label(token_window, text="", justify=tk.LEFT, anchor='w')
    slot_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
    selected_slot = tk.IntVar(value=-1)
    select_button = Button(token_window, text="Select Slot", command=token_window.destroy)
    select_button.pack(pady=10)
    token_window.wait_window()
    return selected_slot.get()

def select_from_token():
    lib_path = r"C:\Windows\System32\cryptoide_pkcs11.dll"  # Adjust this path if needed
    token_info = list_tokens(lib_path)
    if not token_info:
        messagebox.showerror("Error", "No tokens found.")
        return
    slot_index = select_token_slot(token_info)
    if slot_index == -1:
        messagebox.showwarning("Warning", "No slot selected.")
        return
    pin = get_pin_from_user()
    if pin:
        try:
            cert, cert_der = get_certificate_from_token(lib_path, pin, slot_index)
            if cert:
                cert_chain = [cert]
                show_certificates(cert_chain)
            else:
                print("No certificate found on the token.")
        except PyKCS11.PyKCS11Error as e:
            print(f"PyKCS11 error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
    else:
        print("PIN input cancelled")

def select_from_windows():
    try:
        certificates = get_certificates_from_windows_store()
        # Filtering certificates to show only those with specific criteria (e.g., valid usage)
        filtered_certificates = []
        for cert in certificates:
            try:
                if cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE).value.digital_signature:
                    filtered_certificates.append(cert)
            except x509.ExtensionNotFound:
                filtered_certificates.append(cert)  # Include certificates without keyUsage extension

        if filtered_certificates:
            show_certificates(filtered_certificates)
        else:
            print("No relevant certificates found in the Windows cert store.")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    root = tk.Tk()
    root.title("Certificate Selector")

    style = Style()
    style.configure("TButton", font=("Arial", 12), padding=10)

    token_button = Button(root, text="Select from Token", command=select_from_token, style="TButton")
    token_button.pack(pady=10)

    windows_button = Button(root, text="Select from Windows Cert Store", command=select_from_windows, style="TButton")
    windows_button.pack(pady=10)

    root.mainloop()
