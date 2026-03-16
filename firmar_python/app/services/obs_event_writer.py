import time
from contextlib import contextmanager

from app.services.observability import (
    ENTRY_APP_LOG,
    ENTRY_ERROR,
    OPERATION_FAILED,
    OPERATION_SUCCESS,
    STAGE_ERROR,
    STAGE_SUCCESS,
    current_operation,
    finish_operation as finish_operation_v2,
    generate_operation_id as generate_operation_id_v2,
    record_entry,
    stage_scope,
    start_operation as start_operation_v2,
)

STAGE_SIGN_INIT = "sign_init"
STAGE_SIGN_END = "sign_end"
STAGE_SIGN_LORO = "sign_loro"
STAGE_CONTEXT_INIT = "context_init"
STAGE_CONTEXT_END = "context_end"
STAGE_PROTOCOLIZE = "protocolize"
STAGE_UNLOCK_CLOSE = "unlock_close"
STAGE_VALIDATE_PDF = "validate_pdf"
STAGE_VALIDATE_JADES = "validate_jades"
STAGE_VALIDATE_EXPEDIENTE = "validate_expediente"
STAGE_SAVE_PDF = "save_pdf"
STAGE_CREATE_IMAGE = "create_image"
STAGE_CERT_VALIDATE = "cert_validate"
STAGE_MERGE_WATERMARK = "merge_watermark"

STATUS_OK = "ok"
STATUS_ERROR = "error"
STATUS_WARNING = "warning"
STATUS_SKIPPED = "skipped"
STATUS_STARTED = "started"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"


def _map_stage_status(status: str) -> str:
    if status in {STATUS_ERROR, STATUS_FAILED}:
        return STAGE_ERROR
    return STAGE_SUCCESS


def _route_to_operation_key(route: str) -> str:
    normalized = (route or "/").strip("/")
    if not normalized:
        return "http.root"
    return normalized.replace("/", ".")


def generate_operation_id_legacy() -> str:
    return generate_operation_id_v2()


def generate_operation_id() -> str:
    return generate_operation_id_legacy()


def start_operation_legacy(operation_id, route, method="POST", client_ip=None, id_user=None, batch_size=1, attrs=None):
    start_operation_v2(
        operation_id=operation_id,
        operation_key=_route_to_operation_key(route),
        route=route,
        method=method,
        client_ip=client_ip,
        id_user=id_user,
        batch_size=batch_size,
        attrs=attrs,
    )


def start_operation(operation_id, route, method="POST", client_ip=None, id_user=None, batch_size=1, attrs=None):
    start_operation_legacy(operation_id, route, method, client_ip, id_user, batch_size, attrs)


def finish_operation_legacy(operation_id, status=STATUS_COMPLETED, error_message=None, duration_ms=None):
    finish_operation_v2(
        operation_id=operation_id,
        status=OPERATION_FAILED if status in {STATUS_ERROR, STATUS_FAILED} else OPERATION_SUCCESS,
        error_message=error_message,
        duration_ms=duration_ms,
    )


def finish_operation(operation_id, status=STATUS_COMPLETED, error_message=None, duration_ms=None):
    finish_operation_legacy(operation_id, status, error_message, duration_ms)


def log_event(
    stage: str,
    status: str,
    operation_id: str = None,
    document_id: str = None,
    expediente_key: str = None,
    id_user: str = None,
    is_error: bool = False,
    error_code: str = None,
    error_class: str = None,
    message: str = None,
    duration_ms: int = None,
    attrs: dict = None,
):
    payload = {
        "document_id": document_id,
        "expediente_key": expediente_key,
        "id_user": id_user,
        "attrs": attrs or {},
        "duration_ms": duration_ms,
    }

    with stage_scope(stage, stage_label=stage):
        record_entry(
            operation_id=operation_id or current_operation().get("operation_id"),
            entry_kind=ENTRY_ERROR if is_error or status in {STATUS_ERROR, STATUS_FAILED} else ENTRY_APP_LOG,
            title=stage,
            message=message,
            payload=payload,
            error_code=error_code,
            error_class=error_class,
            attrs={"legacy_status": status},
        )


class OperationTracker:
    """Backward-compatible context manager on top of observability V2."""

    def __init__(self, route, method="POST", client_ip=None, id_user=None, batch_size=1, attrs=None):
        self.operation_id = generate_operation_id()
        self._route = route
        self._method = method
        self._client_ip = client_ip
        self._id_user = id_user
        self._batch_size = batch_size
        self._attrs = attrs
        self._t0 = None
        self._error = None

    def __enter__(self):
        self._t0 = time.monotonic()
        start_operation(
            self.operation_id,
            self._route,
            self._method,
            self._client_ip,
            self._id_user,
            self._batch_size,
            self._attrs,
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = int((time.monotonic() - self._t0) * 1000) if self._t0 else None
        if exc_type:
            finish_operation(self.operation_id, STATUS_FAILED, str(exc_val)[:500], elapsed)
        elif self._error:
            finish_operation(self.operation_id, STATUS_FAILED, self._error[:500], elapsed)
        else:
            finish_operation(self.operation_id, STATUS_COMPLETED, duration_ms=elapsed)
        return False

    def set_error(self, msg: str):
        self._error = msg

    def event(self, stage, status, **kwargs):
        kwargs.setdefault("operation_id", self.operation_id)
        log_event(stage, status, **kwargs)
