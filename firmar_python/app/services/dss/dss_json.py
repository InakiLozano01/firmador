# Descripcion: Este modulo contiene las funciones necesarias para firmar un documento JSON con la API de DSS

import logging
import json
import requests
from typing import Dict, Any, Tuple
from app.exceptions.dss_exc import DSSRequestError, DSSResponseError, DSSSigningError
import base64
from .requests import (
    get_data_to_sign_tapir_jades as dss_get_data_jades,
    sign_document_tapir_jades as dss_sign_jades
)

DSSResponse = Dict[str, Any]

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Create console handler with detailed formatting
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
console_handler.setFormatter(formatter)
logger.addHandler(console_handler)

def _make_dss_request(endpoint: str, request_body: Dict[str, Any]) -> DSSResponse:
    """Make a request to the DSS API"""
    try:
        # Log the request
        logger.info("DSS API Request", extra={
            "data": {
                "endpoint": endpoint,
                "request_body": request_body
            }
        })
        
        response = requests.post(f'http://java-webapp:5555/services/rest/signature/one-document/{endpoint}', json=request_body)
        
        # Log the response
        logger.info("DSS API Response", extra={
            "data": {
                "status_code": response.status_code,
                "response": response.json()
            }
        })
        
        if response.status_code != 200:
            raise DSSResponseError(f"DSS API returned status code {response.status_code}")
        
        response_data = response.json()
        if "bytes" not in response_data:
            raise DSSSigningError("DSS API response missing 'bytes' field")
        
        return response_data
        
    except requests.RequestException as e:
        logger.error("DSS API Request Error", extra={
            "data": {
                "endpoint": endpoint,
                "request_body": request_body,
                "error": str(e)
            }
        })
        raise DSSRequestError(f"Failed to connect to DSS API: {str(e)}")
    except Exception as e:
        logger.error("Unexpected DSS API Error", extra={
            "data": {
                "endpoint": endpoint,
                "request_body": request_body,
                "error": str(e)
            }
        })
        raise DSSSigningError(f"Unexpected error during signing: {str(e)}")

def get_data_to_sign_tapir_jades(json_data, certificates, current_time, stamp):
    try:
        # Convert json_data to base64 for logging
        json_str = json_data if isinstance(json_data, str) else base64.b64encode(json.dumps(json_data).encode('utf-8')).decode('utf-8')
        
        logger.info("Starting get_data_to_sign_tapir_jades", extra={
            "data": {
                "json_base64": json_str,
                "certificates": certificates,
                "current_time": current_time,
                "stamp": stamp
            }
        })
        
        # Make the API call - Note the renamed function
        response = dss_get_data_jades(json_str, certificates, current_time, stamp)
        
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
        
        logger.info("Completed get_data_to_sign_tapir_jades", extra={
            "data": {
                "response": {
                    **response,
                    "bytes_preview": response.get("bytes", "")[:100]
                }
            }
        })
        return response
    except Exception as e:
        logger.error("Error in get_data_to_sign_tapir_jades", extra={
            "error": str(e),
            "json_base64": json_str,
            "certificates": certificates,
            "current_time": current_time,
            "stamp": stamp
        })
        raise DSSSigningError(f"Failed to get data to sign with DSS API: {str(e)}")

def sign_document_tapir_jades(json_data, signature_value, certificates, current_time, stamp):
    try:
        # Convert json_data to base64 for logging
        json_str = json_data if isinstance(json_data, str) else base64.b64encode(json.dumps(json_data).encode('utf-8')).decode('utf-8')
        
        logger.info("Starting sign_document_tapir_jades", extra={
            "data": {
                "json_base64": json_str,
                "signature_value": signature_value[:100],  # Preview of signature
                "certificates": certificates,
                "current_time": current_time,
                "stamp": stamp
            }
        })
        
        # Make the API call - Note the renamed function
        response = dss_sign_jades(json_str, signature_value, certificates, current_time, stamp)
        
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
            
        logger.info("Completed sign_document_tapir_jades", extra={
            "data": {
                "response": {
                    **response,
                    "bytes_preview": response.get("bytes", "")[:100]
                }
            }
        })
        return response
    except Exception as e:
        logger.error("Error in sign_document_tapir_jades", extra={
            "error": str(e),
            "json_base64": json_str,
            "certificates": certificates,
            "current_time": current_time,
            "stamp": stamp
        })
        raise DSSSigningError(f"Failed to sign document with DSS API: {str(e)}")