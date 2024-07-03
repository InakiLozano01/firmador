import PyKCS11
import tkinter as tk
from tkinter import simpledialog
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID, AuthorityInformationAccessOID
import requests
import base64



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

def get_certificate_from_token(lib_path, pin):
    pkcs11 = PyKCS11.PyKCS11Lib()
    pkcs11.load(lib_path)
    slots = pkcs11.getSlotList(tokenPresent=True)
    if not slots:
        print("No token found")
        return None

    session = pkcs11.openSession(slots[0], PyKCS11.CKF_SERIAL_SESSION | PyKCS11.CKF_RW_SESSION)
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

def get_full_chain(cert, session, cert_der):
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

def cert_to_base64(cert_der):
    return base64.b64encode(cert_der).decode('ascii')

if __name__ == "__main__":
    lib_path = r"C:\Windows\System32\cryptoide_pkcs11.dll"  # Adjust this path if needed
    
    pin = get_pin_from_user()
    if pin:
        try:
            cert, cert_der = get_certificate_from_token(lib_path, pin)
            if cert:
                session = None  # Session is closed after retrieving the certificate, hence None
                cert_chain = get_full_chain(cert, session, cert_der)
                print(f"\nRetrieved {len(cert_chain)} certificates in the chain:")
                for i, cert_der in enumerate(cert_chain):
                    cert = x509.load_der_x509_certificate(cert_der)
                    print(f"\nCertificate {i + 1}:")
                    print(f"Subject: {cert.subject}")
                    print(f"Issuer: {cert.issuer}")
                    print(f"Not valid before: {cert.not_valid_before_utc}")
                    print(f"Not valid after: {cert.not_valid_after_utc}")
                    print("\nBase64 Encoded Certificate:")
                    print(cert_to_base64(cert_der))
            else:
                print("No certificate found on the token.")
        except PyKCS11.PyKCS11Error as e:
            print(f"PyKCS11 error: {str(e)}")
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
    else:
        print("PIN input cancelled")
