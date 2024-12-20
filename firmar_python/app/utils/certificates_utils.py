# Description: Módulo para extraer información de un certificado X.509

import logging
import base64
import re
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from app.exceptions.validation_exc import (
    SignatureValidationError as CertificateDecodingError,
    DSServiceConnectionError as CertificateLoadError,
    InvalidSignatureDataError as CertificateAttributeError,
    SignatureValidationError as CertificateExtensionError
)

# Configure logging
logger = logging.getLogger(__name__)

def extract_certificate_info(cert_base64):
    """
    Extract information from an X.509 certificate.
    
    Args:
        cert_base64: Base64 encoded certificate string
        
    Returns:
        tuple: (dict with certificate info, status_code)
        
    Raises:
        CertificateDecodingError: When base64 decoding fails
        CertificateLoadError: When certificate loading fails
        CertificateAttributeError: When required attributes are missing
        CertificateExtensionError: When accessing extensions fails
    """
    logger.info("Starting certificate info extraction")
    try:
        logger.debug("Attempting to decode base64 certificate")
        cert_bytes = base64.b64decode(cert_base64)
    except Exception as e:
        logger.error(f"Failed to decode base64 certificate: {str(e)}", exc_info=True)
        raise CertificateDecodingError(f"Failed to decode base64 certificate: {str(e)}")

    try:
        logger.debug("Loading X.509 certificate")
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())
    except Exception as e:
        logger.error(f"Failed to load X.509 certificate: {str(e)}", exc_info=True)
        raise CertificateLoadError(f"Failed to load X.509 certificate: {str(e)}")

    try:
        logger.debug("Extracting CUIL and common name")
        cuil = cert.subject.get_attributes_for_oid(x509.NameOID.SERIAL_NUMBER)[0].value
        common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    except Exception as e:
        logger.error(f"Failed to extract certificate attributes: {str(e)}", exc_info=True)
        raise CertificateAttributeError(f"Failed to extract certificate attributes: {str(e)}")

    try:
        logger.debug("Extracting email from certificate extensions")
        email = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.RFC822Name)
        email = email[0] if email else None
    except Exception as e:
        logger.error(f"Failed to extract email from certificate: {str(e)}", exc_info=True)
        raise CertificateExtensionError(f"Failed to extract email from certificate: {str(e)}")

    cuil = re.sub(r'\D', '', cuil)
    
    response = {
        "status": True,
        "data": {
            "cuil": cuil,
            "common_name": common_name,
            "email": email
        }
    }
    
    logger.info("Successfully extracted certificate info")
    logger.debug(f"Certificate info: {response}")
    return response

def extract_certificate_info_name(cert_base64):
    """
    Extract only the common name from an X.509 certificate.
    
    Args:
        cert_base64: Base64 encoded certificate string
        
    Returns:
        tuple: (dict with certificate name, status_code)
        
    Raises:
        CertificateDecodingError: When base64 decoding fails
        CertificateLoadError: When certificate loading fails
        CertificateAttributeError: When common name is missing
    """
    logger.info("Starting certificate name extraction")
    try:
        logger.debug("Attempting to decode base64 certificate")
        cert_bytes = base64.b64decode(cert_base64)
    except Exception as e:
        logger.error(f"Failed to decode base64 certificate: {str(e)}", exc_info=True)
        raise CertificateDecodingError(f"Failed to decode base64 certificate: {str(e)}")

    try:
        logger.debug("Loading X.509 certificate")
        cert = x509.load_der_x509_certificate(cert_bytes, default_backend())
    except Exception as e:
        logger.error(f"Failed to load X.509 certificate: {str(e)}", exc_info=True)
        raise CertificateLoadError(f"Failed to load X.509 certificate: {str(e)}")

    try:
        logger.debug("Extracting common name")
        common_name = cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)[0].value
    except Exception as e:
        logger.error(f"Failed to extract common name from certificate: {str(e)}", exc_info=True)
        raise CertificateAttributeError(f"Failed to extract common name from certificate: {str(e)}")

    response = {
        "status": True,
        "data": {
            "common_name": common_name
        }
    }
    
    logger.info("Successfully extracted certificate name")
    logger.debug(f"Certificate name: {response}")
    return response