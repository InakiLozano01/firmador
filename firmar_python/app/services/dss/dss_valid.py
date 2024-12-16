# Descripcion: Este modulo contiene las funciones necesarias para validar una firma con la API de DSS

import requests
import base64
import json
from ...exceptions.validation_exc import SignatureValidationError, DSServiceConnectionError, InvalidSignatureDataError

def validate_signature_json(data, signature):
    """
    Validate the signature of a document.

    Args:
        data (str): The data to validate.
        signature (str): The signature to validate.

    Returns:
        dict: The validation result.

    Raises:
        InvalidSignatureDataError: If the input data or signature is invalid.
        DSServiceConnectionError: If there's an error connecting to the DSS service.
        SignatureValidationError: For other validation-related errors.
    """
    if not signature:
        raise InvalidSignatureDataError("Signature data is required")

    body = {
        "signedDocument": {
            "bytes": signature,
            "digestAlgorithm": None,
            "name": "sign.json"
        },
        "originalDocuments": [{
            "bytes": base64.b64encode(json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')).decode('utf-8') if data else None,
            "digestAlgorithm": None,
            "name": "signed.json"
        }],
        "policy": None,
        "evidenceRecords": None,
        "tokenExtractionStrategy": "NONE",
        "signatureId": None
    }
    
    try:
        response = requests.post('http://java-webapp:5555/services/rest/validation/validateSignature', json=body, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError as e:
        raise DSServiceConnectionError(details=str(e))
    except requests.exceptions.RequestException as e:
        raise SignatureValidationError(f"Error validating signature: {str(e)}")
    
def validate_signature_pdf(data):
    """
    Validate the signature of a PDF document.

    Args:
        data (str): The data to validate.

    Returns:
        dict: The validation result.

    Raises:
        InvalidSignatureDataError: If the input data is invalid.
        DSServiceConnectionError: If there's an error connecting to the DSS service.
        SignatureValidationError: For other validation-related errors.
    """
    if not data:
        raise InvalidSignatureDataError("PDF data is required")

    body = {
        "signedDocument": {
            "bytes": data,
            "digestAlgorithm": None,
            "name": "sign.pdf"
        },
        "originalDocuments": [{
            "bytes": None,
            "digestAlgorithm": None,
            "name": None
        }],
        "policy": None,
        "evidenceRecords": None,
        "tokenExtractionStrategy": "NONE",
        "signatureId": None
    }
    
    try:
        response = requests.post('http://java-webapp:5555/services/rest/validation/validateSignature', json=body, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError as e:
        raise DSServiceConnectionError(details=str(e))
    except requests.exceptions.RequestException as e:
        raise SignatureValidationError(f"Error validating PDF signature: {str(e)}")