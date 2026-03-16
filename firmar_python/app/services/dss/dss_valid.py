import base64
import json
import logging
import os

import requests

from app.exceptions.validation_exc import DSServiceConnectionError, InvalidSignatureDataError, SignatureValidationError
from app.services.observability import stage_scope

logger = logging.getLogger(__name__)

DSS_VALIDATE_URL = os.getenv(
    "DSS_VALIDATE_URL",
    "http://java-webapp:5555/services/rest/validation/validateSignature",
)


def _post_validation_request(body, timeout):
    with stage_scope("dss.validate.build_request", "Preparar request DSS"):
        body_size = len(json.dumps(body, separators=(",", ":"), ensure_ascii=False))

    logger.info(
        "dss_validate_request",
        extra={
            "obs_kind": "external_request",
            "obs_payload": {
                "url": DSS_VALIDATE_URL,
                "method": "POST",
                "timeout": timeout,
                "request_size_bytes": body_size,
            },
            "obs_raw_payload": body,
            "obs_capture_raw_payload": True,
            "obs_payload_content_kind": "dss.validateSignature.request",
            "obs_raw_payload_attrs": {"endpoint": "validateSignature", "direction": "request"},
            "obs_attrs": {"dependency": "dss", "endpoint": "validateSignature"},
        },
    )

    with stage_scope("dss.validate.http", "Ejecutar request DSS"):
        response = requests.post(DSS_VALIDATE_URL, json=body, timeout=timeout)

    with stage_scope("dss.validate.parse_response", "Parsear respuesta DSS"):
        payload = response.json() if response.content else None

    logger.info(
        "dss_validate_response",
        extra={
            "obs_kind": "external_response",
            "obs_payload": {
                "url": DSS_VALIDATE_URL,
                "status_code": response.status_code,
                "request_size_bytes": body_size,
            },
            "obs_raw_payload": payload if payload is not None else response.text,
            "obs_capture_raw_payload": True,
            "obs_payload_content_kind": "dss.validateSignature.response",
            "obs_raw_payload_attrs": {"endpoint": "validateSignature", "direction": "response"},
            "obs_attrs": {
                "dependency": "dss",
                "endpoint": "validateSignature",
                "status_code": response.status_code,
                "request_size_bytes": body_size,
            }
        },
    )
    return response, payload


def validate_signature_json(data, signature):
    if not signature:
        raise InvalidSignatureDataError("Signature data is required")

    try:
        data_str = base64.b64encode(
            json.dumps(data, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).decode("utf-8") if data else None

        body = {
            "signedDocument": {
                "bytes": signature,
                "digestAlgorithm": None,
                "name": "sign.json",
            },
            "originalDocuments": [{
                "bytes": data_str,
                "digestAlgorithm": None,
                "name": "signed.json",
            }],
            "policy": None,
            "evidenceRecords": None,
            "tokenExtractionStrategy": "NONE",
            "signatureId": None,
        }

        response, payload = _post_validation_request(body, timeout=30)
        if response.status_code != 200:
            return None, response.status_code
        return payload, 200
    except requests.exceptions.ConnectionError as exc:
        raise DSServiceConnectionError(details=str(exc)) from exc
    except requests.exceptions.RequestException as exc:
        raise SignatureValidationError(f"Error validating signature: {str(exc)}") from exc
    except Exception as exc:
        raise SignatureValidationError(f"Unexpected error during validation: {str(exc)}") from exc


def validate_signature_pdf(data):
    if not data:
        raise InvalidSignatureDataError("PDF data is required")

    body = {
        "signedDocument": {
            "bytes": data,
            "digestAlgorithm": None,
            "name": "sign.pdf",
        },
        "originalDocuments": [{
            "bytes": None,
            "digestAlgorithm": None,
            "name": None,
        }],
        "policy": None,
        "evidenceRecords": None,
        "tokenExtractionStrategy": "NONE",
        "signatureId": None,
    }

    try:
        response, payload = _post_validation_request(body, timeout=60)
        if response.status_code == 500:
            error_content = response.text
            if "Document format not recognized" in error_content or "format not recognized" in error_content:
                error = SignatureValidationError(f"PDF_FORMAT_ERROR: {error_content[:500]}")
                error.is_format_error = True
                raise error
            raise SignatureValidationError(f"Validation service error (500): {error_content[:500]}")
        response.raise_for_status()
        return payload
    except requests.exceptions.ConnectionError as exc:
        raise DSServiceConnectionError(details=str(exc)) from exc
    except requests.exceptions.RequestException as exc:
        raise SignatureValidationError(f"Error validating PDF signature: {str(exc)}") from exc


def validation_analyze(validation_report):
    try:
        if not validation_report:
            return None, 400

        signatures = validation_report.get("signatures", [])
        if not signatures:
            return None, 400

        result = []
        for sig in signatures:
            conclusion = sig.get("conclusion", {})
            indication = conclusion.get("indication", "")
            result.append({
                "valid": indication == "TOTAL_PASSED",
                "certs_valid": indication != "INDETERMINATE_CERTIFICATE_CHAIN_GENERAL_FAILURE",
                "indication": indication,
                "subindication": conclusion.get("subIndication", ""),
                "errors": conclusion.get("errors", []),
            })

        return result, 200
    except Exception as exc:
        raise SignatureValidationError(f"Error analyzing validation report: {str(exc)}") from exc
