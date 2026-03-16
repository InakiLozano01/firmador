import base64
import hashlib
import logging
from typing import Optional

from .requests import (
    get_data_to_sign_tapir as dss_get_data_tapir,
    sign_document_tapir as dss_sign_tapir,
    get_data_to_sign_own as dss_get_data_own,
    sign_document_own as dss_sign_own,
)
from ...exceptions.dss_exc import DSSResponseError, DSSSigningError

logger = logging.getLogger(__name__)


def _payload_hash(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _normalize_pdf(pdf):
    return pdf if isinstance(pdf, str) else base64.b64encode(pdf).decode("utf-8")


def _handle_pdf_response(response, *, endpoint: str):
    if isinstance(response, tuple):
        payload, status_code = response
    else:
        payload, status_code = response, 200

    if status_code != 200:
        raise DSSResponseError(f"DSS API returned status code {status_code} for {endpoint}")
    if not isinstance(payload, dict) or "bytes" not in payload:
        raise DSSResponseError(f"Invalid response format from DSS API for {endpoint}")
    return payload


def get_data_to_sign_certificate(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count=None):
    try:
        pdf_str = _normalize_pdf(pdf)
        logger.info(
            "dss_get_data_to_sign_certificate",
            extra={
                "obs_attrs": {
                    "dependency": "dss",
                    "endpoint": "getDataToSign",
                    "pdf_sha256": _payload_hash(pdf_str),
                    "image_sha256": _payload_hash(encoded_image),
                    "page_count": page_count,
                }
            },
        )
        response = dss_get_data_own(
            pdf_str,
            certificates,
            current_time,
            field_id,
            stamp,
            encoded_image,
            page_count,
        )
        return _handle_pdf_response(response, endpoint="getDataToSign")
    except Exception as exc:
        logger.error(
            "dss_get_data_to_sign_certificate_failed",
            exc_info=True,
            extra={"obs_attrs": {"dependency": "dss", "endpoint": "getDataToSign"}},
        )
        raise DSSSigningError(f"Failed to get data to sign with DSS API: {str(exc)}") from exc


def sign_document_certificate(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image, page_count=None):
    try:
        pdf_str = _normalize_pdf(pdf)
        logger.info(
            "dss_sign_document_certificate",
            extra={
                "obs_attrs": {
                    "dependency": "dss",
                    "endpoint": "signDocument",
                    "pdf_sha256": _payload_hash(pdf_str),
                    "image_sha256": _payload_hash(encoded_image),
                    "signature_len": len(signature_value or ""),
                    "page_count": page_count,
                }
            },
        )
        response = dss_sign_own(
            pdf_str,
            signature_value,
            certificates,
            current_time,
            field_id,
            stamp,
            encoded_image,
            page_count,
        )
        return _handle_pdf_response(response, endpoint="signDocument")
    except Exception as exc:
        logger.error(
            "dss_sign_document_certificate_failed",
            exc_info=True,
            extra={"obs_attrs": {"dependency": "dss", "endpoint": "signDocument"}},
        )
        raise DSSSigningError(f"Failed to sign document with DSS API: {str(exc)}") from exc


def get_data_to_sign_token(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count=None):
    try:
        pdf_str = _normalize_pdf(pdf)
        response = dss_get_data_tapir(
            pdf_str,
            certificates,
            current_time,
            field_id,
            stamp,
            encoded_image,
            page_count,
        )
        return _handle_pdf_response(response, endpoint="getDataToSign")
    except Exception as exc:
        logger.error(
            "dss_get_data_to_sign_token_failed",
            exc_info=True,
            extra={"obs_attrs": {"dependency": "dss", "endpoint": "getDataToSign"}},
        )
        raise DSSSigningError(f"Failed to get data to sign with DSS API: {str(exc)}") from exc


def sign_document_token(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image, page_count=None):
    try:
        pdf_str = _normalize_pdf(pdf)
        response = dss_sign_tapir(
            pdf_str,
            signature_value,
            certificates,
            current_time,
            field_id,
            stamp,
            encoded_image,
            page_count,
        )
        return _handle_pdf_response(response, endpoint="signDocument")
    except Exception as exc:
        logger.error(
            "dss_sign_document_token_failed",
            exc_info=True,
            extra={"obs_attrs": {"dependency": "dss", "endpoint": "signDocument"}},
        )
        raise DSSSigningError(f"Failed to sign document with DSS API: {str(exc)}") from exc
