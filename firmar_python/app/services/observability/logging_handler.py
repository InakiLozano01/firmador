from __future__ import annotations

import logging
import traceback
from typing import Any, Dict

from app.config.settings import settings

from .constants import ENTRY_APP_LOG, ENTRY_ERROR
from .context import get_current_operation_id, is_logging_suppressed, suppress_logging
from .recorder import record_entry
from .sanitizer import sanitize_log_message, sanitize_stacktrace

STANDARD_ATTRS = {
    "args",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "taskName",
    "thread",
    "threadName",
}


class ObservabilityLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if not get_current_operation_id() or is_logging_suppressed():
            return

        if record.name.startswith("app.services.observability"):
            return

        try:
            entry_kind = getattr(record, "obs_kind", None)
            if not entry_kind:
                entry_kind = ENTRY_ERROR if record.levelno >= logging.ERROR else ENTRY_APP_LOG
            if record.levelno < logging.INFO and entry_kind == ENTRY_APP_LOG and not settings.OBS_PERSIST_DEBUG_LOGS:
                return

            payload = getattr(record, "obs_payload", None)
            raw_payload = getattr(record, "obs_raw_payload", None)
            attrs = getattr(record, "obs_attrs", None) or {}

            if payload is None:
                extras = self._extract_extra_payload(record)
                payload = extras or None

            stacktrace = None
            if record.exc_info:
                stacktrace = sanitize_stacktrace("".join(traceback.format_exception(*record.exc_info)))
            elif record.stack_info:
                stacktrace = sanitize_stacktrace(record.stack_info)

            with suppress_logging():
                record_entry(
                    entry_kind=entry_kind,
                    title=record.levelname,
                    message=sanitize_log_message(record.getMessage()),
                    payload=payload,
                    raw_payload=raw_payload,
                    capture_raw_payload=getattr(record, "obs_capture_raw_payload", False),
                    payload_content_kind=getattr(record, "obs_payload_content_kind", None),
                    raw_payload_attrs=getattr(record, "obs_raw_payload_attrs", None),
                    log_level=record.levelname.lower(),
                    logger_name=record.name,
                    error_code=getattr(record, "error_code", attrs.get("error_code")),
                    error_class=record.exc_info[0].__name__ if record.exc_info else getattr(record, "error_class", None),
                    stacktrace=stacktrace,
                    attrs={
                        "module": record.module,
                        "pathname": record.pathname,
                        "lineno": record.lineno,
                        **attrs,
                    },
                )
        except Exception:
            pass

    @staticmethod
    def _extract_extra_payload(record: logging.LogRecord) -> Dict[str, Any]:
        payload = {}
        for key, value in record.__dict__.items():
            if key in STANDARD_ATTRS or key.startswith("_"):
                continue
            if key in {
                "obs_kind",
                "obs_payload",
                "obs_raw_payload",
                "obs_capture_raw_payload",
                "obs_payload_content_kind",
                "obs_raw_payload_attrs",
                "obs_attrs",
            }:
                continue
            if value is None:
                continue
            payload[key] = value
        return payload


def install_observability_logging() -> None:
    root = logging.getLogger()
    for handler in root.handlers:
        if isinstance(handler, ObservabilityLogHandler):
            return
    root.addHandler(ObservabilityLogHandler())
