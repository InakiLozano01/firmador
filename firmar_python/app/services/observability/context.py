from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Dict, Optional

_current_operation_id: ContextVar[Optional[str]] = ContextVar("obs_operation_id", default=None)
_current_operation_key: ContextVar[Optional[str]] = ContextVar("obs_operation_key", default=None)
_current_operation_status: ContextVar[Optional[str]] = ContextVar("obs_operation_status", default=None)
_current_operation_error: ContextVar[Optional[str]] = ContextVar("obs_operation_error", default=None)
_current_subject_id: ContextVar[Optional[int]] = ContextVar("obs_subject_id", default=None)
_current_stage_id: ContextVar[Optional[int]] = ContextVar("obs_stage_id", default=None)
_logging_suppressed: ContextVar[bool] = ContextVar("obs_logging_suppressed", default=False)


def get_current_operation_id() -> Optional[str]:
    return _current_operation_id.get()


def get_current_operation_key() -> Optional[str]:
    return _current_operation_key.get()


def get_current_operation_status() -> Optional[str]:
    return _current_operation_status.get()


def get_current_operation_error() -> Optional[str]:
    return _current_operation_error.get()


def get_current_subject_id() -> Optional[int]:
    return _current_subject_id.get()


def get_current_stage_id() -> Optional[int]:
    return _current_stage_id.get()


def is_logging_suppressed() -> bool:
    return _logging_suppressed.get()


def bind_operation(operation_id: str, operation_key: Optional[str] = None, status: Optional[str] = None):
    return {
        "operation_id": _current_operation_id.set(operation_id),
        "operation_key": _current_operation_key.set(operation_key),
        "operation_status": _current_operation_status.set(status),
        "operation_error": _current_operation_error.set(None),
    }


def bind_subject(subject_id: Optional[int]):
    return {"subject_id": _current_subject_id.set(subject_id)}


def bind_stage(stage_id: Optional[int]):
    return {"stage_id": _current_stage_id.set(stage_id)}


def set_current_operation_status(status: Optional[str], error_message: Optional[str] = None) -> None:
    _current_operation_status.set(status)
    if error_message is not None:
        _current_operation_error.set(error_message)


def reset_bindings(tokens: Dict[str, Any]) -> None:
    if "stage_id" in tokens:
        _current_stage_id.reset(tokens["stage_id"])
    if "subject_id" in tokens:
        _current_subject_id.reset(tokens["subject_id"])
    if "operation_error" in tokens:
        _current_operation_error.reset(tokens["operation_error"])
    if "operation_status" in tokens:
        _current_operation_status.reset(tokens["operation_status"])
    if "operation_key" in tokens:
        _current_operation_key.reset(tokens["operation_key"])
    if "operation_id" in tokens:
        _current_operation_id.reset(tokens["operation_id"])


def current_context_snapshot() -> Dict[str, Any]:
    return {
        "operation_id": get_current_operation_id(),
        "operation_key": get_current_operation_key(),
        "operation_status": get_current_operation_status(),
        "operation_error": get_current_operation_error(),
        "subject_id": get_current_subject_id(),
        "stage_id": get_current_stage_id(),
    }


@contextmanager
def suppress_logging():
    token = _logging_suppressed.set(True)
    try:
        yield
    finally:
        _logging_suppressed.reset(token)
