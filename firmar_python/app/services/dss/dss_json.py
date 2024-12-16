# Descripcion: Este modulo contiene las funciones necesarias para firmar un documento JSON con la API de DSS

import logging
import json
import requests
from typing import Dict, Any, Tuple
from app.exceptions.dss_exc import DSSRequestError, DSSResponseError, DSSSigningError
from app.services.dss.requests import build_json_request_body

DSSResponse = Dict[str, Any]

def _make_dss_request(endpoint: str, request_body: Dict[str, Any]) -> DSSResponse:
    """Make a request to the DSS API"""
    try:
        response = requests.post(f'http://java-webapp:5555/services/rest/signature/one-document/{endpoint}', json=request_body)
        
        if response.status_code != 200:
            raise DSSResponseError(f"DSS API returned status code {response.status_code}")
        
        response_data = response.json()
        if "bytes" not in response_data:
            raise DSSSigningError("DSS API response missing 'bytes' field")
        
        return response_data
        
    except requests.RequestException as e:
        logging.error(f"DSS API request error: {str(e)}")
        raise DSSRequestError(f"Failed to connect to DSS API: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error in DSS API request: {str(e)}")
        raise DSSSigningError(f"Unexpected error during signing: {str(e)}")

def get_data_to_sign_tapir_jades(
    json_data: str,
    certificates: Dict[str, Any],
    current_time: int,
    stamp: str
) -> DSSResponse:
    """Get data to sign with token using JAdES"""
    request_body = build_json_request_body(json_data, certificates, current_time, stamp)
    return _make_dss_request('getDataToSign', request_body)

def sign_document_tapir_jades(
    json_data: str,
    signature_value: str,
    certificates: Dict[str, Any],
    current_time: int,
    stamp: str
) -> DSSResponse:
    """Sign document with token using JAdES"""
    request_body = build_json_request_body(json_data, certificates, current_time, stamp, signature_value)
    return _make_dss_request('signDocument', request_body)