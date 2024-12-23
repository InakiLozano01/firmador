# Descripcion: Este modulo contiene las funciones necesarias para validar una firma con la API de DSS

import requests
import base64
import json
import logging
from app.exceptions.validation_exc import SignatureValidationError, DSServiceConnectionError, InvalidSignatureDataError

logger = logging.getLogger(__name__)

def validate_signature_json(data, signature):
    """
    Validate the signature of a JSON document.

    Args:
        data (dict): The JSON data to validate
        signature (str): The signature to validate

    Returns:
        tuple: (validation_result, status_code)

    Raises:
        InvalidSignatureDataError: If input data is invalid
        DSServiceConnectionError: If service is unreachable
        SignatureValidationError: For other validation errors
    """
    if not signature:
        logger.error("Missing signature data")
        raise InvalidSignatureDataError("Signature data is required")

    try:
        # Convert data to base64 if needed
        data_str = base64.b64encode(
            json.dumps(data, separators=(',', ':'), ensure_ascii=False).encode('utf-8')
        ).decode('utf-8') if data else None

        body = {
            "signedDocument": {
                "bytes": signature,
                "digestAlgorithm": None,
                "name": "sign.json"
            },
            "originalDocuments": [{
                "bytes": data_str,
                "digestAlgorithm": None,
                "name": "signed.json"
            }],
            "policy": None,
            "evidenceRecords": None,
            "tokenExtractionStrategy": "NONE",
            "signatureId": None
        }

        logger.debug("Sending validation request to DSS service", extra={
            "request_body": body
        })
        
        response = requests.post(
            'http://java-webapp:5555/services/rest/validation/validateSignature',
            json=body,
            timeout=10
        )
        
        if response.status_code != 200:
            logger.error(f"DSS service returned status code {response.status_code}")
            return None, response.status_code
            
        return response.json(), 200
        
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Failed to connect to DSS service: {str(e)}")
        raise DSServiceConnectionError(details=str(e))
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error during validation: {str(e)}")
        raise SignatureValidationError(f"Error validating signature: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during validation: {str(e)}")
        raise SignatureValidationError(f"Unexpected error during validation: {str(e)}")

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

def validation_analyze(validation_report):
    """
    Analyze the validation report from DSS.

    Args:
        validation_report (dict): The validation report to analyze

    Returns:
        tuple: (analysis_result, status_code)

    Raises:
        SignatureValidationError: If analysis fails
    """
    try:
        if not validation_report:
            logger.error("Empty validation report")
            return None, 400

        signatures = validation_report.get('signatures', [])
        if not signatures:
            logger.error("No signatures found in validation report")
            return None, 400

        result = []
        for sig in signatures:
            conclusion = sig.get('conclusion', {})
            indication = conclusion.get('indication', '')
            
            analysis = {
                'valid': indication == 'TOTAL_PASSED',
                'certs_valid': indication != 'INDETERMINATE_CERTIFICATE_CHAIN_GENERAL_FAILURE',
                'indication': indication,
                'subindication': conclusion.get('subIndication', ''),
                'errors': conclusion.get('errors', [])
            }
            result.append(analysis)

        logger.debug("Validation analysis completed", extra={
            "analysis_result": result
        })
        
        return result, 200

    except Exception as e:
        logger.error(f"Error analyzing validation report: {str(e)}")
        raise SignatureValidationError(f"Error analyzing validation report: {str(e)}")