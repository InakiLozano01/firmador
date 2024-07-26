import PyKCS11
import tkinter as tk
from tkinter import simpledialog, messagebox
from tkinter import ttk
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
import requests
import base64
from cryptography.hazmat.backends import default_backend
import win32crypt

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
                    return x509.load_der_x509_certificate(response.content, default_backend())
                except ValueError:
                    print("Failed to parse DER format, trying PEM...")
                    return x509.load_pem_x509_certificate(response.content, default_backend())
    except x509.ExtensionNotFound:
        print("No Authority Information Access extension found.")
    except Exception as e:
        print(f"Error fetching issuer certificate: {str(e)}")
    return None

def get_certificate_from_token(lib_path, pin, slot):
    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load(lib_path)
    session = pkcs11.openSession(slot, PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
    session.login(pin)

    cert_attributes = [PyKCS11.CKA_CLASS, PyKCS11.CKA_CERTIFICATE_TYPE, PyKCS11.CKA_VALUE]

    for obj in session.findObjects():
        attributes = session.getAttributeValue(obj, cert_attributes)
        if attributes[0] == PyKCS11.CKO_CERTIFICATE:
            cert_der = bytes(attributes[2])
            cert = x509.load_der_x509_certificate(cert_der, default_backend())
            print(f"Found certificate on token: {cert.subject}")
            session.logout()
            session.closeSession()
            return cert, cert_der

    session.logout()
    session.closeSession()
    return None, None

def get_certificates_from_windows_keystore():
    cert_store = win32crypt.CertOpenSystemStore(None, "MY")
    certs = []
    cert_context = win32crypt.CertEnumCertificatesInStore(cert_store, None)
    while cert_context:
        cert = x509.load_der_x509_certificate(cert_context[0], default_backend())
        certs.append(cert)
        cert_context = win32crypt.CertEnumCertificatesInStore(cert_store, cert_context)
    win32crypt.CertCloseStore(cert_store, 0)
    return certs

def cert_to_base64(cert_der):
    return base64.b64encode(cert_der).decode('ascii')

def get_full_chain(cert, cert_der):
    chain = [cert_der]
    current_cert = cert
    while True:
        if current_cert.issuer == current_cert.subject:
            print("Reached self-signed certificate. Chain building complete.")
            break
        issuer_cert = get_issuer_cert(current_cert)
        if issuer_cert is None:
            print("Failed to fetch issuer certificate automatically. Exiting chain building.")
            break
        issuer_cert_der = issuer_cert.public_bytes(serialization.Encoding.DER)
        if issuer_cert_der in chain:
            break  # Prevent loops
        chain.append(issuer_cert_der)
        print(f"Found issuer certificate: {issuer_cert.subject}")
        current_cert = issuer_cert
    return chain

def display_cert_chain(chain):
    print(f"\nRetrieved {len(chain)} certificates in the chain:")
    for i, cert_der in enumerate(chain):
        cert = x509.load_der_x509_certificate(cert_der, default_backend())
        print(f"\nCertificate {i + 1}:")
        print(f"Subject: {cert.subject}")
        print(f"Issuer: {cert.issuer}")
        print(f"Not valid before: {cert.not_valid_before}")
        print(f"Not valid after: {cert.not_valid_after}")
        print("\nBase64 Encoded Certificate:")
        print(cert_to_base64(cert_der))

def select_slot():
    def on_select(event=None):
        selected_slot = slot_listbox.curselection()
        if selected_slot:
            slot = slots[selected_slot[0]]
            root.destroy()
            pin = get_pin_from_user()
            if pin:
                cert, cert_der = get_certificate_from_token(lib_path, pin, slot)
                if cert:
                    cert_chain = get_full_chain(cert, cert_der)
                    display_cert_chain(cert_chain)
                else:
                    print("No certificate found on the token.")
            else:
                print("PIN input cancelled")
    
    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load(lib_path)
    global slots
    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        print("No token found")
        return

    root = tk.Tk()
    root.title("Select Slot")
    tk.Label(root, text="Select a slot:").pack()
    slot_listbox = tk.Listbox(root)
    for i, slot in enumerate(slots):
        slot_listbox.insert(tk.END, f"Slot {i}: {slot}")
    slot_listbox.pack()
    slot_listbox.bind("<Double-1>", on_select)
    tk.Button(root, text="Select", command=on_select).pack()
    root.mainloop()

def select_windows_cert():
    def on_select(event=None):
        selected_cert = cert_listbox.curselection()
        if selected_cert:
            cert = windows_certs[selected_cert[0]]
            root.destroy()
            cert_der = cert.public_bytes(serialization.Encoding.DER)
            cert_chain = get_full_chain(cert, cert_der)
            display_cert_chain(cert_chain)

    global windows_certs
    windows_certs = get_certificates_from_windows_keystore()
    if not windows_certs:
        print("No certificates found in the Windows Keystore.")
        return

    root = tk.Tk()
    root.title("Select Certificate")
    tk.Label(root, text="Select a certificate:").pack()
    cert_listbox = tk.Listbox(root)
    for i, cert in enumerate(windows_certs):
        cert_listbox.insert(tk.END, f"{i}: {cert.subject}")
    cert_listbox.pack()
    cert_listbox.bind("<Double-1>", on_select)
    tk.Button(root, text="Select", command=on_select).pack()
    root.mainloop()

def main():
    root = tk.Tk()
    root.title("Select Source")

    def on_token_select():
        root.destroy()
        select_slot()

    def on_windows_select():
        root.destroy()
        select_windows_cert()

    tk.Button(root, text="Select Token", command=on_token_select).pack(pady=10)
    tk.Button(root, text="Select Windows Certificate", command=on_windows_select).pack(pady=10)
    root.mainloop()

if __name__ == "__main__":
    lib_path = r"C:\Windows\System32\cryptoide_pkcs11.dll"  # Adjust this path if needed
    main()
