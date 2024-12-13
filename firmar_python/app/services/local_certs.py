from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend
import base64
import os
from typing import Dict, List, Tuple, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class CertificateError(Exception):
    """Custom exception for certificate-related errors"""
    pass

class SignatureError(Exception):
    """Custom exception for signature-related errors"""
    pass

def _load_environment_variables() -> Tuple[str, str, str]:
    """Load and validate required environment variables"""
    private_key_password = os.getenv('PRIVATE_KEY_PASSWORD')
    private_key_path = os.getenv('PRIVATE_KEY_PATH')
    certificate_path = os.getenv('CERTIFICATE_PATH')
    
    if not all([private_key_password, private_key_path, certificate_path]):
        raise CertificateError("Missing required environment variables")
    
    return private_key_password, private_key_path, certificate_path

def _load_private_key(key_path: str, password: str) -> rsa.RSAPrivateKey:
    """Load private key from file"""
    try:
        with open(key_path, "rb") as key_file:
            return load_pem_private_key(
                key_file.read(),
                password=password.encode(),
                backend=default_backend()
            )
    except Exception as e:
        raise SignatureError(f"Failed to load private key: {str(e)}")

def _load_certificate(cert_path: str) -> bytes:
    """Load certificate from file"""
    try:
        with open(cert_path, "rb") as cert_file:
            return cert_file.read()
    except Exception as e:
        raise CertificateError(f"Failed to read certificate file: {str(e)}")

def get_signature_value_own(data_to_sign: str) -> str:
    """
    Sign data using local private key
    
    Args:
        data_to_sign: Base64 encoded data to sign
        
    Returns:
        Base64 encoded signature
        
    Raises:
        SignatureError: If signing process fails
    """
    try:
        private_key_password, private_key_path, _ = _load_environment_variables()
        private_key = _load_private_key(private_key_path, private_key_password)
        
        # Decode input data and generate signature
        data_to_sign_bytes = base64.b64decode(data_to_sign)
        signature = private_key.sign(
            data_to_sign_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        
        return base64.b64encode(signature).decode("utf-8")
    except Exception as e:
        raise SignatureError(f"Failed to sign data: {str(e)}")

def get_certificate_from_local() -> Dict[str, Union[str, List[str]]]:
    """
    Get local certificate in base64 format
    
    Returns:
        Dictionary containing certificate and certificate chain in base64
        
    Raises:
        CertificateError: If certificate loading fails
    """
    try:
        _, _, certificate_path = _load_environment_variables()
        certificate_data = _load_certificate(certificate_path)
        
        # Encode certificate data
        cert_base64 = base64.b64encode(certificate_data).decode("utf-8")
        
        return {
            "certificate": cert_base64,
            "certificateChain": [cert_base64]  # Single certificate chain for simplification
        }
    except Exception as e:
        raise CertificateError(f"Failed to process certificate: {str(e)}")
