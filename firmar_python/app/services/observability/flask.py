from __future__ import annotations

import json
import traceback
from contextvars import copy_context
from functools import wraps
from typing import Any, Callable, Tuple

from flask import jsonify, make_response, request
from app.config.settings import settings

from .constants import (
    ENTRY_ERROR,
    ENTRY_HTTP_REQUEST,
    ENTRY_HTTP_RESPONSE,
    OPERATION_FAILED,
    OPERATION_REJECTED,
    OPERATION_RUNNING,
    OPERATION_SUCCESS,
)
from .context import (
    bind_operation,
    get_current_operation_error,
    get_current_operation_id,
    get_current_operation_key,
    get_current_operation_status,
    get_current_stage_id,
    get_current_subject_id,
    reset_bindings,
)
from .recorder import finish_operation, record_entry, start_operation, update_operation


def current_operation():
    return {
        "operation_id": get_current_operation_id(),
        "operation_key": get_current_operation_key(),
        "operation_status": get_current_operation_status(),
    }


def current_subject():
    return {"subject_id": get_current_subject_id()}


def current_stage():
    return {"stage_id": get_current_stage_id()}


def _client_ip() -> str | None:
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _is_sensitive_route() -> bool:
    return request.path in {
        "/firmalote",
        "/firmaloteend",
        "/firmaloro",
        "/firmajades",
        "/firmajadesend",
        "/validatepdfs",
        "/validarjades",
        "/validar_expediente",
    }


def _request_payload() -> Tuple[dict[str, Any], Any, str | None]:
    raw_body = request.get_data(cache=True)
    capture_body = settings.OBS_CAPTURE_HTTP_BODIES
    sensitive_route = _is_sensitive_route()
    if sensitive_route and not settings.OBS_CAPTURE_SIGNING_HTTP_BODIES:
        capture_body = False

    parsed_json = request.get_json(silent=True) if capture_body else None
    if capture_body:
        if parsed_json is not None:
            body_value: Any = parsed_json
        elif raw_body:
            body_value = raw_body.decode("utf-8", errors="replace")
        else:
            body_value = None
    else:
        body_value = {
            "captured": False,
            "bytes": len(raw_body or b""),
            "content_type": request.content_type,
        }

    return {
        "headers": dict(request.headers),
        "query": request.args.to_dict(flat=False),
        "body": body_value,
    }, (raw_body if raw_body and (sensitive_route or settings.OBS_CAPTURE_HTTP_BODIES) else None), "http.request.body"


def _response_payload(response) -> Tuple[dict[str, Any], Any, str | None]:
    capture_body = settings.OBS_CAPTURE_HTTP_BODIES
    sensitive_route = _is_sensitive_route()
    if sensitive_route and not settings.OBS_CAPTURE_SIGNING_HTTP_BODIES:
        capture_body = False

    body_text = response.get_data(as_text=True)
    if capture_body:
        payload_body: Any = body_text
        if response.mimetype == "application/json" and body_text:
            try:
                payload_body = json.loads(body_text)
            except json.JSONDecodeError:
                payload_body = body_text
    else:
        payload_body = {
            "captured": False,
            "bytes": len(response.get_data() or b""),
            "content_type": response.content_type,
        }

    raw_response = response.get_data()
    return {
        "headers": dict(response.headers),
        "body": payload_body,
    }, (raw_response if raw_response and (sensitive_route or settings.OBS_CAPTURE_HTTP_BODIES) else None), "http.response.body"


def observe_http_operation(operation_key: str) -> Callable:
    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(*args, **kwargs):
            raw_body = request.get_data(cache=True)
            operation_id = start_operation(
                operation_key=operation_key,
                route=request.path,
                method=request.method,
                client_ip=_client_ip(),
                request_content_type=request.content_type,
                request_size_bytes=len(raw_body or b""),
                attrs={"view": view_func.__name__},
            )
            tokens = bind_operation(operation_id, operation_key, OPERATION_RUNNING)

            try:
                request_payload, request_raw_payload, request_content_kind = _request_payload()
                record_entry(
                    entry_kind=ENTRY_HTTP_REQUEST,
                    title=f"{request.method} {request.path}",
                    message="Incoming HTTP request",
                    payload=request_payload,
                    raw_payload=request_raw_payload,
                    capture_raw_payload=request_raw_payload is not None,
                    payload_content_kind=request_content_kind,
                    http_method=request.method,
                    url=request.url,
                    route=request.path,
                    attrs={"view": view_func.__name__},
                )

                response = make_response(view_func(*args, **kwargs))
                response_bytes = len(response.get_data() or b"")

                update_operation(
                    http_status_code=response.status_code,
                    response_content_type=response.content_type,
                    response_size_bytes=response_bytes,
                )
                response_payload, response_raw_payload, response_content_kind = _response_payload(response)
                record_entry(
                    entry_kind=ENTRY_HTTP_RESPONSE,
                    title=f"{response.status_code} {request.path}",
                    message="Outgoing HTTP response",
                    payload=response_payload,
                    raw_payload=response_raw_payload,
                    capture_raw_payload=response_raw_payload is not None,
                    payload_content_kind=response_content_kind,
                    http_method=request.method,
                    url=request.url,
                    route=request.path,
                    status_code=response.status_code,
                )

                status = get_current_operation_status()
                if status == OPERATION_RUNNING or not status:
                    if response.status_code >= 500:
                        status = OPERATION_FAILED
                    elif response.status_code >= 400:
                        status = OPERATION_REJECTED
                    else:
                        status = OPERATION_SUCCESS

                finish_operation(status=status, error_message=get_current_operation_error())
                return response
            except Exception as exc:
                stacktrace = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
                error_response = jsonify(
                    {
                        "status": False,
                        "message": "Internal server error",
                        "errors": [{"message": "Internal server error"}],
                    }
                )
                error_response.status_code = 500

                record_entry(
                    entry_kind=ENTRY_ERROR,
                    title="Unhandled exception",
                    message=str(exc)[:500],
                    payload={"view": view_func.__name__},
                    http_method=request.method,
                    url=request.url,
                    route=request.path,
                    status_code=500,
                    error_class=type(exc).__name__,
                    stacktrace=stacktrace,
                )
                error_response_payload, error_response_raw, error_response_kind = _response_payload(error_response)
                record_entry(
                    entry_kind=ENTRY_HTTP_RESPONSE,
                    title=f"500 {request.path}",
                    message="Outgoing HTTP response",
                    payload=error_response_payload,
                    raw_payload=error_response_raw,
                    capture_raw_payload=error_response_raw is not None,
                    payload_content_kind=error_response_kind,
                    http_method=request.method,
                    url=request.url,
                    route=request.path,
                    status_code=500,
                )
                update_operation(
                    http_status_code=500,
                    response_content_type=error_response.content_type,
                    response_size_bytes=len(error_response.get_data() or b""),
                )
                finish_operation(status=OPERATION_FAILED, error_message=str(exc)[:500])
                return error_response
            finally:
                reset_bindings(tokens)

        return wrapper

    return decorator


def submit_with_observability_context(executor, fn, *args, **kwargs):
    ctx = copy_context()
    return executor.submit(ctx.run, fn, *args, **kwargs)
