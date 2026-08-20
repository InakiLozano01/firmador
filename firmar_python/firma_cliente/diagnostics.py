import json
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any


LOGGER_NAME = "tuquito"
SENSITIVE_FIELD_FRAGMENTS = (
    "pin",
    "payload",
    "data_to_sign",
    "signature",
    "certificate",
)
logger = logging.getLogger(LOGGER_NAME)
logger.setLevel(logging.INFO)
logger.propagate = False


def _default_log_dir() -> Path:
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return Path(root) / "Tuquito" / "logs"
    return Path.home() / ".tuquito" / "logs"


def configure_diagnostics(
    log_dir: str | os.PathLike[str] | None = None,
    *,
    force: bool = False,
) -> str:
    if logger.handlers and not force:
        handler = logger.handlers[0]
        return str(getattr(handler, "baseFilename", ""))

    if force:
        for handler in list(logger.handlers):
            handler.close()
            logger.removeHandler(handler)

    destination = Path(log_dir) if log_dir else _default_log_dir()
    destination.mkdir(parents=True, exist_ok=True)
    log_path = destination / "tuquito.log"
    handler = RotatingFileHandler(
        log_path,
        maxBytes=2 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(message)s"
    ))
    logger.addHandler(handler)
    if sys.stderr is not None:
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(message)s"
        ))
        logger.addHandler(console_handler)
    return str(log_path)


def _safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    safe = {}
    for key, value in fields.items():
        normalized_key = key.lower()
        if any(fragment in normalized_key for fragment in SENSITIVE_FIELD_FRAGMENTS):
            safe[key] = "[REDACTED]"
        else:
            safe[key] = value
    return safe


def log_event(event: str, **fields: Any) -> None:
    record = {"event": event, **_safe_fields(fields)}
    logger.info(json.dumps(record, ensure_ascii=False, default=str))


def flush_diagnostics() -> None:
    for handler in logger.handlers:
        handler.flush()


def close_diagnostics() -> None:
    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)
