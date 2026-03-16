# Archivo para cerrar el PDF con los datos para los campos de formu

import requests
import base64
import json
import os
from app.exceptions.dss_exc import PDFClosingError, DSSRequestError
import logging

logger = logging.getLogger(__name__)

DSS_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DSS_CONNECT_TIMEOUT_SECONDS", "5"))
DSS_READ_TIMEOUT_SECONDS = int(os.getenv("DSS_READ_TIMEOUT_SECONDS", "60"))
DSS_TIMEOUT = (DSS_CONNECT_TIMEOUT_SECONDS, DSS_READ_TIMEOUT_SECONDS)

def close_pdf(pdf_to_close, json_field_values):
    """
    Cierra el PDF.

    Args:
        pdf_to_close (str): Base64 encoded PDF to close.
        json_field_values (str): JSON string of field values.

    Returns:
        str: Base64 encoded closed PDF.

    Raises:
        PDFClosingError: When there is an error closing the PDF.
        DSSRequestError: When there is an error in the API request.
    """
    try:
        data = {
            'fileBase64': pdf_to_close,
            'fileName': "documento.pdf",
            'fieldValues': json_field_values
        }
        logger.info(
            "Close PDF request",
            extra={
                "obs_kind": "external_request",
                "obs_payload": {
                    "url": "http://java-webapp:5555/pdf/update",
                    "method": "POST",
                    "body": data,
                    "timeout": DSS_TIMEOUT,
                },
            },
        )
        response = requests.post(
            'http://java-webapp:5555/pdf/update',
            json=data,
            timeout=DSS_TIMEOUT,
        )
        logger.info(
            "Close PDF response",
            extra={
                "obs_kind": "external_response",
                "obs_payload": {
                    "url": "http://java-webapp:5555/pdf/update",
                    "status_code": response.status_code,
                    "body": response.text[:1000],
                },
            },
        )
        response.raise_for_status()
        return base64.b64encode(response.content).decode("utf-8")
    except requests.exceptions.RequestException as e:
        logging.error("Error in API request: %s", str(e))
        raise DSSRequestError(f"Error in API request: {str(e)}")
    except Exception as e:
        logging.error("Unexpected error in close_pdf: %s", str(e))
        raise PDFClosingError(f"An unexpected error occurred while closing PDF: {str(e)}")
