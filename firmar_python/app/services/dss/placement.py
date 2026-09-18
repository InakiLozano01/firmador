from typing import Any, Dict

from ...exceptions.dss_exc import DSSResponseError
from .requests import _build_pdf_document, _pdf_parameters, _post_dss_json


def _unwrap_dss_response(response, *, endpoint: str):
    if isinstance(response, tuple):
        payload, status_code = response
    else:
        payload, status_code = response, 200
    if status_code != 200:
        raise DSSResponseError(f"DSS API returned status code {status_code} for {endpoint}")
    if not isinstance(payload, dict) or "bytes" not in payload:
        raise DSSResponseError(f"Invalid response format from DSS API for {endpoint}")
    return payload


def _parameters_with_placement(
    *,
    certificates: Dict[str, Any],
    current_time: int,
    field_id: str,
    stamp: str,
    encoded_image: str,
    page_count: int,
    origin_x=None,
    origin_y=None,
    width=None,
    height=None,
    page=None,
) -> Dict[str, Any]:
    parameters = _pdf_parameters(
        certificates=certificates,
        current_time=current_time,
        field_id=field_id,
        stamp=stamp,
        encoded_image=encoded_image,
        page_count=page_count,
    )
    field = parameters["imageParameters"]["fieldParameters"]
    field["fieldId"] = "" if field_id in (None, "") else f"{field_id}"
    if origin_x is not None:
        field["originX"] = origin_x
    if origin_y is not None:
        field["originY"] = origin_y
    if width is not None:
        field["width"] = width
    if height is not None:
        field["height"] = height
    if page is not None:
        field["page"] = int(page)
    return parameters


def get_data_to_sign_with_placement(
    pdf,
    certificates,
    current_time,
    field_id,
    stamp,
    encoded_image,
    page_count,
    origin_x=None,
    origin_y=None,
    width=None,
    height=None,
    page=None,
):
    body = {
        "parameters": _parameters_with_placement(
            certificates=certificates,
            current_time=current_time,
            field_id=field_id,
            stamp=stamp,
            encoded_image=encoded_image,
            page_count=page_count,
            origin_x=origin_x,
            origin_y=origin_y,
            width=width,
            height=height,
            page=page,
        ),
        "toSignDocument": _build_pdf_document(pdf),
    }
    return _unwrap_dss_response(_post_dss_json("getDataToSign", body), endpoint="getDataToSign")


def sign_document_with_placement(
    pdf,
    signature_value,
    certificates,
    current_time,
    field_id,
    stamp,
    encoded_image,
    page_count,
    origin_x=None,
    origin_y=None,
    width=None,
    height=None,
    page=None,
):
    body = {
        "parameters": _parameters_with_placement(
            certificates=certificates,
            current_time=current_time,
            field_id=field_id,
            stamp=stamp,
            encoded_image=encoded_image,
            page_count=page_count,
            origin_x=origin_x,
            origin_y=origin_y,
            width=width,
            height=height,
            page=page,
        ),
        "signatureValue": {
            "algorithm": "RSA_SHA256",
            "value": signature_value,
        },
        "toSignDocument": _build_pdf_document(pdf),
    }
    return _unwrap_dss_response(_post_dss_json("signDocument", body), endpoint="signDocument")
