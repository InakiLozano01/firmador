import requests
import logging
from typing import Dict, Any, Tuple
from app.exceptions.dss_exc import DSSRequestError, DSSResponseError, DSSSigningError
from app.services.dss.requests import build_request_body

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

def get_data_to_sign_certificate(
    pdf: str,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str
) -> DSSResponse:
    """Get data to sign with certificate"""
    request_body = build_request_body(
        pdf=pdf,
        certificates=certificates,
        current_time=current_time,
        field_id=field_id,
        stamp=stamp,
        encoded_image=encoded_image
    )
    return _make_dss_request('getDataToSign', request_body)

def sign_document_certificate(
    pdf: str,
    signature_value: str,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str
) -> DSSResponse:
    """Sign document with certificate"""
    request_body = build_request_body(
        pdf=pdf,
        certificates=certificates,
        current_time=current_time,
        field_id=field_id,
        stamp=stamp,
        encoded_image=encoded_image,
        signature_value=signature_value
    )
    return _make_dss_request('signDocument', request_body)

def get_data_to_sign_token(
    pdf: str,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str
) -> DSSResponse:
    """Get data to sign with token"""
    request_body = build_request_body(
        pdf=pdf,
        certificates=certificates,
        current_time=current_time,
        field_id=field_id,
        stamp=stamp,
        encoded_image=encoded_image
    )
    return _make_dss_request('getDataToSign', request_body)

def sign_document_token(
    pdf: str,
    signature_value: str,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str
) -> DSSResponse:
    """Sign document with token"""
    request_body = build_request_body(
        pdf=pdf,
        certificates=certificates,
        current_time=current_time,
        field_id=field_id,
        stamp=stamp,
        encoded_image=encoded_image,
        signature_value=signature_value
    )
    return _make_dss_request('signDocument', request_body)
