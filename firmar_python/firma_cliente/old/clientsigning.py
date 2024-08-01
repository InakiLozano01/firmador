import PyKCS11
import tkinter as tk
from tkinter import simpledialog, filedialog
import base64
import hashlib
from OpenSSL import crypto

def get_pin_from_user():
    root = tk.Tk()
    root.withdraw()  # Hide the root window
    pin = simpledialog.askstring("Token PIN", "Enter PIN for the token:", show='*')
    root.destroy()  # Destroy the root window
    return pin

def get_private_key_and_certificates(token_library_path):
    try:
        pkcs11 = PyKCS11.PyKCS11Lib()
        pkcs11.load(token_library_path)
        
        slots = pkcs11.getSlotList()
        if not slots:
            raise Exception("No slots found.")
        
        session = pkcs11.openSession(slots[0], PyKCS11.CKF_RW_SESSION | PyKCS11.CKF_SERIAL_SESSION)
        print("Session opened successfully.")
        
        # User authentication
        pin = get_pin_from_user()
        if not pin:
            raise Exception("PIN entry cancelled by user.")
        
        session.login(pin)
        print("Login successful.")
        
        # Retrieve objects (private key and certificate)
        private_key_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)])
        certificate_objects = session.findObjects([(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)])
        
        if not private_key_objects or not certificate_objects:
            raise Exception("No private key or certificate found on the token.")
        
        private_key = private_key_objects[0]
        certificate = certificate_objects[0]
        
        # Export certificate
        cert_der = bytes(session.getAttributeValue(certificate, [PyKCS11.CKA_VALUE])[0])
        cert_base64 = base64.b64encode(cert_der).decode('utf-8')
        
        return session, private_key, cert_base64
    except PyKCS11.PyKCS11Error as e:
        print(f"PyKCS11 error occurred: {e}")
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
        raise

def correct_base64_padding(data):
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += '=' * (4 - missing_padding)
    return data

def sign_data_with_private_key(session, private_key, data_to_sign_base64):
    data_to_sign_base64 = correct_base64_padding(data_to_sign_base64)
    data_to_sign_bytes = base64.b64decode(data_to_sign_base64)
    
    mechanism = PyKCS11.Mechanism(PyKCS11.CKM_SHA256_RSA_PKCS, None)
    signature = bytes(session.sign(private_key, data_to_sign_bytes, mechanism))
    
    # Convert the signature to base64 for sending to DSS
    signature_base64 = base64.b64encode(signature).decode("utf-8")
    return signature_base64

# Example usage:
token_library_path = r"C:\Windows\System32\cryptoide_pkcs11.dll"  # Adjust path as necessary

try:
    session, private_key, certificate = get_private_key_and_certificates(token_library_path)
    print(f"Certificate: {certificate}\n")
    
    path = filedialog.askopenfilename(filetypes=[("PDF files", "*.pdf")])
    digest_base64 = "Algo"
    print(f"Digest: {digest_base64}")

    # Sign data
    signature_base64 = sign_data_with_private_key(session, private_key, digest_base64)
    print(f"Signature: {signature_base64}")
    
    session.logout()
    session.closeSession()
    
except Exception as e:
    print(f"An error occurred: {e}")


