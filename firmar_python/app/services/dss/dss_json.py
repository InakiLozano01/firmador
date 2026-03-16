import hashlib
import logging

from app.exceptions.dss_exc import DSSResponseError, DSSSigningError

from .requests import (
    get_data_to_sign_tapir_jades as dss_get_data_jades,
    sign_document_tapir_jades as dss_sign_jades,
)

logger = logging.getLogger(__name__)


def _payload_hash(value):
    if not value:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def _handle_response(response, endpoint: str):
    if isinstance(response, tuple):
        payload, status_code = response
    else:
        payload, status_code = response, 200

    if status_code != 200:
        raise DSSResponseError(f"DSS API returned status code {status_code} for {endpoint}")
    if not isinstance(payload, dict) or "bytes" not in payload:
        raise DSSResponseError(f"Invalid response format from DSS API for {endpoint}")
    return payload


def get_data_to_sign_tapir_jades(json_data, certificates, current_time, stamp):
    try:
        logger.info(
            "dss_get_data_to_sign_jades",
            extra={
                "obs_attrs": {
                    "dependency": "dss",
                    "endpoint": "getDataToSign",
                    "json_sha256": _payload_hash(json_data),
                }
            },
        )
        response = dss_get_data_jades(json_data, certificates, current_time, stamp)
        return _handle_response(response, "getDataToSign")
    except Exception as exc:
        logger.error(
            "dss_get_data_to_sign_jades_failed",
            exc_info=True,
            extra={"obs_attrs": {"dependency": "dss", "endpoint": "getDataToSign"}},
        )
        raise DSSSigningError(f"Failed to get data to sign with DSS API: {str(exc)}") from exc


def sign_document_tapir_jades(json_data, signature_value, certificates, current_time, stamp):
    try:
        logger.info(
            "dss_sign_document_jades",
            extra={
                "obs_attrs": {
                    "dependency": "dss",
                    "endpoint": "signDocument",
                    "json_sha256": _payload_hash(json_data),
                    "signature_len": len(signature_value or ""),
                }
            },
        )
        response = dss_sign_jades(json_data, signature_value, certificates, current_time, stamp)
        return _handle_response(response, "signDocument")
    except Exception as exc:
        logger.error(
            "dss_sign_document_jades_failed",
            exc_info=True,
            extra={"obs_attrs": {"dependency": "dss", "endpoint": "signDocument"}},
        )
        raise DSSSigningError(f"Failed to sign document with DSS API: {str(exc)}") from exc
