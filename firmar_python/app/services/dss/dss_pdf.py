import base64
import logging
import hashlib
import json
from .requests import (
    get_data_to_sign_tapir as dss_get_data_tapir,
    sign_document_tapir as dss_sign_tapir,
    get_data_to_sign_own as dss_get_data_own,
    sign_document_own as dss_sign_own
)
from ...exceptions.dss_exc import DSSRequestError, DSSResponseError, DSSSigningError

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create a file handler
file_handler = logging.FileHandler('dss_pdf.log')
file_handler.setLevel(logging.DEBUG)

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

# Add the handler to the logger
logger.addHandler(file_handler)

def log_image_details(logger, prefix: str, image_data: str, extra_info: dict = None):
    """Helper function to log image details consistently"""
    if not image_data:
        logger.info(f"{prefix} - No image data")
        return
        
    try:
        info = {
            "length": len(image_data),
            "preview": image_data[:100],
            "hash": hashlib.sha256(image_data.encode()).hexdigest(),
            **(extra_info or {})
        }
        logger.info(f"{prefix} - Image details", extra={"image_data": info})
    except Exception as e:
        logger.error(f"Error logging image details: {str(e)}")

def get_data_to_sign_certificate(pdf, certificates, current_time, field_id, stamp, encoded_image):
    try:
        # Log input image
        log_image_details(logger, "INPUT_IMAGE", encoded_image, {
            "field_id": field_id,
            "stamp": stamp
        })
        
        # Convert PDF if needed and log it
        if isinstance(pdf, str):
            pdf_str = pdf
        else:
            pdf_str = base64.b64encode(pdf).decode('utf-8')
        
        log_image_details(logger, "INPUT_PDF", pdf_str)
            
        # Make the API call
        response = dss_get_data_own(pdf_str, certificates, current_time, field_id, stamp, encoded_image)
        
        # Log the raw response
        logger.debug("Raw DSS API Response", extra={
            "response": json.dumps(response) if isinstance(response, dict) else str(response)
        })
        
        if isinstance(response, tuple):
            response, status_code = response
            if status_code != 200:
                raise DSSResponseError(response.get("message", "Unknown error"))
                
        if not isinstance(response, dict) or "bytes" not in response:
            raise DSSResponseError("Invalid response format from DSS API")
            
        # Log the response bytes
        log_image_details(logger, "OUTPUT_BYTES", response.get("bytes", ""))
        
        return response
        
    except Exception as e:
        logger.error("Error in get_data_to_sign_certificate", extra={
            "error": str(e),
            "input_image_hash": hashlib.sha256(encoded_image.encode()).hexdigest() if encoded_image else None
        })
        raise DSSSigningError(f"Failed to get data to sign with DSS API: {str(e)}")
    
def sign_document_certificate(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image):
    try:
        # Log input image
        log_image_details(logger, "INPUT_IMAGE", encoded_image, {
            "field_id": field_id,
            "stamp": stamp
        })
        
        # Log signature value
        logger.info("Signature Value", extra={
            "signature_value": {
                "length": len(signature_value),
                "preview": signature_value[:100]
            }
        })
        
        # Convert PDF if needed and log it
        if isinstance(pdf, str):
            pdf_str = pdf
        else:
            pdf_str = base64.b64encode(pdf).decode('utf-8')
            
        log_image_details(logger, "INPUT_PDF", pdf_str)
        
        # Make the API call
        response = dss_sign_own(pdf_str, signature_value, certificates, current_time, field_id, stamp, encoded_image)
        
        # Log the raw response
        logger.debug("Raw DSS API Response", extra={
            "response": json.dumps(response) if isinstance(response, dict) else str(response)
        })
        
        if isinstance(response, tuple):
            response, status_code = response
            if status_code != 200:
                raise DSSResponseError(response.get("message", "Unknown error"))
                
        if not isinstance(response, dict) or "bytes" not in response:
            raise DSSResponseError("Invalid response format from DSS API")
            
        # Log the response bytes
        log_image_details(logger, "OUTPUT_BYTES", response.get("bytes", ""))
        
        return response
        
    except Exception as e:
        logger.error("Error in sign_document_certificate", extra={
            "error": str(e),
            "input_image_hash": hashlib.sha256(encoded_image.encode()).hexdigest() if encoded_image else None
        })
        raise DSSSigningError(f"Failed to sign document with DSS API: {str(e)}")

def get_data_to_sign_token(pdf, certificates, current_time, field_id, stamp, encoded_image):
    try:
        # If pdf is already a string, assume it's base64 encoded
        if isinstance(pdf, str):
            pdf_str = pdf
        else:
            pdf_str = base64.b64encode(pdf).decode('utf-8')
            
        response = dss_get_data_tapir(pdf_str, certificates, current_time, field_id, stamp, encoded_image)
        if isinstance(response, tuple):
            response, status_code = response
            if status_code != 200:
                raise DSSResponseError(response.get("message", "Unknown error"))
        if not isinstance(response, dict) or "bytes" not in response:
            raise DSSResponseError("Invalid response format from DSS API")
        return response
    except Exception as e:
        logging.error(f"Error in get_data_to_sign_token: {str(e)}")
        raise DSSSigningError(f"Failed to get data to sign with DSS API: {str(e)}")

def sign_document_token(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image):
    try:
        # If pdf is already a string, assume it's base64 encoded
        if isinstance(pdf, str):
            pdf_str = pdf
        else:
            pdf_str = base64.b64encode(pdf).decode('utf-8')
            
        response = dss_sign_tapir(pdf_str, signature_value, certificates, current_time, field_id, stamp, encoded_image)
        if isinstance(response, tuple):
            response, status_code = response
            if status_code != 200:
                raise DSSResponseError(response.get("message", "Unknown error"))
        if not isinstance(response, dict) or "bytes" not in response:
            raise DSSResponseError("Invalid response format from DSS API")
        return response
    except Exception as e:
        logging.error(f"Error in sign_document_token: {str(e)}")
        raise DSSSigningError(f"Failed to sign document with DSS API: {str(e)}")
