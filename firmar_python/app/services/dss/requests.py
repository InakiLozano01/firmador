from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter

from app.config.settings import settings

logger = logging.getLogger(__name__)

DSS_CONNECT_TIMEOUT_SECONDS = int(os.getenv("DSS_CONNECT_TIMEOUT_SECONDS", "5"))
DSS_READ_TIMEOUT_SECONDS = int(os.getenv("DSS_READ_TIMEOUT_SECONDS", "60"))
DSS_TIMEOUT = (DSS_CONNECT_TIMEOUT_SECONDS, DSS_READ_TIMEOUT_SECONDS)
DSS_BASE_URL = os.getenv(
    "DSS_BASE_URL",
    "http://java-webapp:5555/services/rest/signature/one-document",
).rstrip("/")


@dataclass(frozen=True)
class DssClient:
    session: requests.Session
    base_url: str
    timeout: Tuple[int, int]


_SESSION_LOCK = threading.Lock()
_DSS_CLIENT: Optional[DssClient] = None


def _build_http_adapter() -> HTTPAdapter:
    return HTTPAdapter(
        pool_connections=settings.DSS_POOL_MAXSIZE,
        pool_maxsize=settings.DSS_POOL_MAXSIZE,
        max_retries=0,
        pool_block=True,
    )


def _get_dss_client() -> DssClient:
    global _DSS_CLIENT
    if _DSS_CLIENT is not None:
        return _DSS_CLIENT

    with _SESSION_LOCK:
        if _DSS_CLIENT is not None:
            return _DSS_CLIENT

        session = requests.Session()
        adapter = _build_http_adapter()
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _DSS_CLIENT = DssClient(session=session, base_url=DSS_BASE_URL, timeout=DSS_TIMEOUT)
        return _DSS_CLIENT


def _certificate_parameters(certificates: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "signingCertificate": {"encodedCertificate": certificates["certificate"]},
        "certificateChain": [
            {"encodedCertificate": cert} for cert in certificates.get("certificateChain", [])
        ],
    }


def _pdf_parameters(
    *,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str,
    page_count: int,
) -> Dict[str, Any]:
    return {
        **_certificate_parameters(certificates),
        "detachedContents": None,
        "asicContainerType": None,
        "signatureLevel": "PAdES_BASELINE_B",
        "signaturePackaging": "ENVELOPED",
        "embedXML": False,
        "manifestSignature": False,
        "jwsSerializationType": None,
        "sigDMechanism": None,
        "signatureAlgorithm": "RSA_SHA256",
        "digestAlgorithm": "SHA256",
        "encryptionAlgorithm": "RSA",
        "referenceDigestAlgorithm": None,
        "maskGenerationFunction": None,
        "contentTimestamps": None,
        "contentTimestampParameters": {
            "digestAlgorithm": "SHA256",
            "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
            "timestampContainerForm": None,
        },
        "signatureTimestampParameters": {
            "digestAlgorithm": "SHA256",
            "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
            "timestampContainerForm": None,
        },
        "archiveTimestampParameters": {
            "digestAlgorithm": "SHA256",
            "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
            "timestampContainerForm": None,
        },
        "signWithExpiredCertificate": False,
        "generateTBSWithoutCertificate": False,
        "imageParameters": {
            "alignmentHorizontal": None,
            "alignmentVertical": None,
            "imageScaling": "ZOOM_AND_CENTER",
            "backgroundColor": None,
            "dpi": 200,
            "image": {
                "bytes": encoded_image,
                "name": "image.png",
            },
            "fieldParameters": {
                "fieldId": f"{field_id}",
                "originX": 0,
                "originY": 0,
                "width": None,
                "height": None,
                "rotation": None,
                "page": int(page_count),
            },
            "textParameters": None,
            "zoom": None,
        },
        "signatureIdToCounterSign": None,
        "blevelParams": {
            "trustAnchorBPPolicy": True,
            "signingDate": current_time,
            "claimedSignerRoles": [f"{stamp}"],
            "policyId": None,
            "policyQualifier": None,
            "policyDescription": None,
            "policyDigestAlgorithm": None,
            "policyDigestValue": None,
            "policySpuri": None,
            "commitmentTypeIndications": None,
            "signerLocationPostalAddress": [
                "Congreso 180",
                "4000 San Miguel de Tucumán",
                "Tucumán",
                "AR",
            ],
            "signerLocationPostalCode": "4000",
            "signerLocationLocality": "San Miguel de Tucumán",
            "signerLocationStateOrProvince": "Tucumán",
            "signerLocationCountry": "AR",
            "signerLocationStreet": "Congreso 180",
        },
    }


def _jades_parameters(*, certificates: Dict[str, Any], current_time: int, stamp: str) -> Dict[str, Any]:
    return {
        **_certificate_parameters(certificates),
        "detachedContents": None,
        "asicContainerType": None,
        "signatureLevel": "JAdES_BASELINE_B",
        "signaturePackaging": "DETACHED",
        "embedXML": False,
        "manifestSignature": False,
        "jwsSerializationType": None,
        "sigDMechanism": "OBJECT_ID_BY_URI",
        "signatureAlgorithm": None,
        "digestAlgorithm": "SHA256",
        "encryptionAlgorithm": None,
        "referenceDigestAlgorithm": None,
        "contentTimestamps": None,
        "contentTimestampParameters": {
            "digestAlgorithm": "SHA256",
            "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
            "timestampContainerForm": None,
        },
        "signatureTimestampParameters": {
            "digestAlgorithm": "SHA256",
            "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
            "timestampContainerForm": None,
        },
        "archiveTimestampParameters": {
            "digestAlgorithm": "SHA256",
            "canonicalizationMethod": "http://www.w3.org/2001/10/xml-exc-c14n#",
            "timestampContainerForm": None,
        },
        "signWithExpiredCertificate": False,
        "generateTBSWithoutCertificate": False,
        "blevelParams": {
            "trustAnchorBPPolicy": True,
            "signingDate": current_time,
            "claimedSignerRoles": [f"{stamp}"],
            "policyId": None,
            "policyQualifier": None,
            "policyDescription": None,
            "policyDigestAlgorithm": None,
            "policyDigestValue": None,
            "policySpuri": None,
            "commitmentTypeIndications": None,
            "signerLocationPostalAddress": [
                "Congreso 180",
                "4000 San Miguel de Tucumán",
                "Tucumán",
                "AR",
            ],
            "signerLocationPostalCode": "4000",
            "signerLocationLocality": "San Miguel de Tucumán",
            "signerLocationStateOrProvince": "Tucumán",
            "signerLocationCountry": "AR",
            "signerLocationStreet": "Congreso 180",
        },
    }


def _post_dss_json(endpoint: str, body: Dict[str, Any]) -> Tuple[Dict[str, Any], int]:
    client = _get_dss_client()
    url = f"{client.base_url}/{endpoint.lstrip('/')}"
    started = time.monotonic()
    logger.info(
        "dss_request",
        extra={
            "obs_kind": "external_request",
            "obs_payload": {
                "url": url,
                "method": "POST",
                "timeout": client.timeout,
                "body_size_hint": len(str(body)),
            },
            "obs_raw_payload": body,
            "obs_capture_raw_payload": True,
            "obs_payload_content_kind": f"dss.{endpoint}.request",
            "obs_raw_payload_attrs": {"endpoint": endpoint, "direction": "request"},
            "obs_attrs": {"dependency": "dss", "endpoint": endpoint},
        },
    )
    response = client.session.post(url, json=body, timeout=client.timeout)
    duration_ms = int((time.monotonic() - started) * 1000)

    response_json: Optional[Dict[str, Any]] = None
    try:
        parsed = response.json()
        response_json = parsed if isinstance(parsed, dict) else {"data": parsed}
    except Exception:
        response_json = None

    logger.info(
        "dss_response",
        extra={
            "obs_kind": "external_response",
            "obs_payload": {
                "url": url,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "bytes_field_size": len(str((response_json or {}).get("bytes", ""))) if response_json else None,
            },
            "obs_raw_payload": response_json if response_json is not None else response.text,
            "obs_capture_raw_payload": True,
            "obs_payload_content_kind": f"dss.{endpoint}.response",
            "obs_raw_payload_attrs": {"endpoint": endpoint, "direction": "response"},
            "obs_attrs": {
                "dependency": "dss",
                "endpoint": endpoint,
                "duration_ms": duration_ms,
                "status_code": response.status_code,
            },
        },
    )

    if response_json is None:
        return {"status": False, "message": "Failed to parse DSS response."}, response.status_code
    return response_json, response.status_code


def _build_pdf_document(pdf: str) -> Dict[str, Any]:
    return {
        "bytes": pdf,
        "digestAlgorithm": None,
        "name": "document.pdf",
    }


def _build_json_document(json_b64: str) -> Dict[str, Any]:
    return {
        "bytes": json_b64,
        "digestAlgorithm": None,
        "name": "document.json",
    }


def get_data_to_sign_own(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count):
    body = {
        "parameters": _pdf_parameters(
            certificates=certificates,
            current_time=current_time,
            field_id=field_id,
            stamp=stamp,
            encoded_image=encoded_image,
            page_count=page_count,
        ),
        "toSignDocument": _build_pdf_document(pdf),
    }
    return _post_dss_json("getDataToSign", body)


def sign_document_own(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image, page_count):
    body = {
        "parameters": _pdf_parameters(
            certificates=certificates,
            current_time=current_time,
            field_id=field_id,
            stamp=stamp,
            encoded_image=encoded_image,
            page_count=page_count,
        ),
        "signatureValue": {
            "algorithm": "RSA_SHA256",
            "value": signature_value,
        },
        "toSignDocument": _build_pdf_document(pdf),
    }
    return _post_dss_json("signDocument", body)


def get_data_to_sign_tapir(pdf, certificates, current_time, field_id, stamp, encoded_image, page_count):
    body = {
        "parameters": _pdf_parameters(
            certificates=certificates,
            current_time=current_time,
            field_id=field_id,
            stamp=stamp,
            encoded_image=encoded_image,
            page_count=page_count,
        ),
        "toSignDocument": _build_pdf_document(pdf),
    }
    return _post_dss_json("getDataToSign", body)


def sign_document_tapir(pdf, signature_value, certificates, current_time, field_id, stamp, encoded_image, page_count):
    body = {
        "parameters": _pdf_parameters(
            certificates=certificates,
            current_time=current_time,
            field_id=field_id,
            stamp=stamp,
            encoded_image=encoded_image,
            page_count=page_count,
        ),
        "signatureValue": {
            "algorithm": "RSA_SHA256",
            "value": signature_value,
        },
        "toSignDocument": _build_pdf_document(pdf),
    }
    return _post_dss_json("signDocument", body)


def get_data_to_sign_tapir_jades(json_b64, certificates, current_time, stamp):
    body = {
        "parameters": _jades_parameters(
            certificates=certificates,
            current_time=current_time,
            stamp=stamp,
        ),
        "toSignDocument": _build_json_document(json_b64),
    }
    return _post_dss_json("getDataToSign", body)


def sign_document_tapir_jades(json_b64, signature_value, certificates, current_time, stamp):
    body = {
        "parameters": _jades_parameters(
            certificates=certificates,
            current_time=current_time,
            stamp=stamp,
        ),
        "signatureValue": {
            "algorithm": "RSA_SHA256",
            "value": signature_value,
        },
        "toSignDocument": _build_json_document(json_b64),
    }
    return _post_dss_json("signDocument", body)
