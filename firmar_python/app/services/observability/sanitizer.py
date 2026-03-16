from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, Tuple

MAX_PAYLOAD_TEXT = 4096
MAX_STACKTRACE_TEXT = 8192
MAX_LOG_MESSAGE_TEXT = 1200
MAX_LOG_SCAN_TEXT = 16384
MAX_PAYLOAD_JSON_BYTES = 64 * 1024
MAX_DEPTH = 6
MAX_LIST_ITEMS = 25
PREVIEW_LENGTH = 64

SENSITIVE_KEYS = {
    "authorization",
    "bytes",
    "certificate",
    "certificatechain",
    "cookie",
    "pdf",
    "pin",
    "set-cookie",
    "signature",
    "signaturevalue",
}

BASE64_RE = re.compile(r"^[A-Za-z0-9+/=\r\n]+$")
LONG_BASE64_RE = re.compile(r"[A-Za-z0-9+/=\r\n]{128,}")


def truncate_text(value: Any, limit: int = MAX_PAYLOAD_TEXT) -> str | None:
    if value is None:
        return None
    text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


def sanitize_stacktrace(value: Any) -> str | None:
    return truncate_text(value, MAX_STACKTRACE_TEXT)


def sanitize_log_message(value: Any, limit: int = MAX_LOG_MESSAGE_TEXT) -> str | None:
    if value is None:
        return None

    text = str(value)
    if len(text) > MAX_LOG_SCAN_TEXT:
        text = text[:MAX_LOG_SCAN_TEXT] + "..."

    def replace_base64(match: re.Match[str]) -> str:
        candidate = match.group(0)
        compact = candidate.replace("\r", "").replace("\n", "")
        if not _looks_like_base64(compact):
            return candidate
        summary = _masked_summary(compact)
        return (
            f"[trimmed-base64 size={summary['size']} "
            f"sha256={summary['sha256']} preview={summary['preview']!r}]"
        )

    text = LONG_BASE64_RE.sub(replace_base64, text)
    return truncate_text(text, limit)


def _payload_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _as_bytes(value: Any) -> bytes:
    if value is None:
        return b""
    if isinstance(value, bytes):
        return value
    return str(value).encode("utf-8", errors="replace")


def _serialize_payload(value: Any) -> Tuple[bytes, str]:
    if value is None:
        return b"", "application/octet-stream"
    if isinstance(value, bytes):
        return value, "application/octet-stream"
    if isinstance(value, str):
        return value.encode("utf-8", errors="replace"), "text/plain"
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, default=str).encode("utf-8"), "application/json"
    return str(value).encode("utf-8", errors="replace"), "text/plain"


def _looks_like_base64(value: str) -> bool:
    if len(value) < 128 or len(value) % 4 != 0:
        return False
    return bool(BASE64_RE.match(value))


def _masked_summary(value: Any) -> Dict[str, Any]:
    data = _as_bytes(value)
    preview = value[:PREVIEW_LENGTH] if isinstance(value, str) else None
    return {
        "masked": True,
        "preview": preview,
        "size": len(data),
        "sha256": _payload_hash(data),
    }


def _sanitize_value(value: Any, key: str | None = None, depth: int = 0) -> Any:
    if depth > MAX_DEPTH:
        return {"truncated": True, "reason": "max_depth"}

    normalized_key = (key or "").lower().replace("_", "").replace("-", "")
    if normalized_key in SENSITIVE_KEYS:
        return _masked_summary(value)

    if isinstance(value, dict):
        return {
            str(k): _sanitize_value(v, key=str(k), depth=depth + 1)
            for k, v in value.items()
        }

    if isinstance(value, (list, tuple, set)):
        items = list(value)
        sanitized_items = [_sanitize_value(item, depth=depth + 1) for item in items[:MAX_LIST_ITEMS]]
        if len(items) > MAX_LIST_ITEMS:
            sanitized_items.append({"truncated": True, "remaining_items": len(items) - MAX_LIST_ITEMS})
        return sanitized_items

    if isinstance(value, bytes):
        return _masked_summary(value)

    if isinstance(value, str):
        if normalized_key in SENSITIVE_KEYS or _looks_like_base64(value):
            return _masked_summary(value)
        return truncate_text(value, MAX_PAYLOAD_TEXT)

    if isinstance(value, (int, float, bool)) or value is None:
        return value

    return truncate_text(value, MAX_PAYLOAD_TEXT)


def sanitize_payload(
    value: Any,
    *,
    capture_raw: bool = False,
    raw_payload: Any = None,
    content_kind: str | None = None,
    max_raw_bytes: int = 5 * 1024 * 1024,
) -> Dict[str, Any]:
    if value is None and raw_payload is None:
        return {
            "payload_json": None,
            "payload_text": None,
            "payload_hash": None,
            "payload_bytes": None,
            "payload_truncated": False,
            "sanitized": True,
            "raw_payload": None,
        }

    raw_bytes, inferred_content_kind = _serialize_payload(
        json.dumps(value, ensure_ascii=False, default=str) if not isinstance(value, (str, bytes)) else value
    )
    sanitized_value = _sanitize_value(value)
    payload_text = None

    if isinstance(sanitized_value, (dict, list)):
        encoded = json.dumps(sanitized_value, ensure_ascii=False, default=str)
        payload_json = sanitized_value
        payload_text = truncate_text(encoded, MAX_PAYLOAD_TEXT)
        payload_truncated = len(encoded.encode("utf-8")) > MAX_PAYLOAD_JSON_BYTES
        if payload_truncated:
            payload_json = {
                "truncated": True,
                "size": len(raw_bytes),
                "sha256": _payload_hash(raw_bytes),
                "preview": truncate_text(payload_text, 1024),
            }
    else:
        payload_json = None
        payload_text = truncate_text(sanitized_value, MAX_PAYLOAD_TEXT)
        payload_truncated = isinstance(sanitized_value, str) and len(sanitized_value) > MAX_PAYLOAD_TEXT

    capture = None
    if capture_raw and (raw_payload is not None or value is not None):
        capture_bytes, source_content_kind = _serialize_payload(raw_payload if raw_payload is not None else value)
        stored_bytes = capture_bytes[:max(0, max_raw_bytes)]
        capture = {
            "bytes": stored_bytes,
            "payload_hash": _payload_hash(capture_bytes),
            "raw_bytes": len(capture_bytes),
            "stored_bytes": len(stored_bytes),
            "truncated": len(capture_bytes) > len(stored_bytes),
            "content_kind": content_kind or source_content_kind or inferred_content_kind,
        }

    return {
        "payload_json": payload_json,
        "payload_text": payload_text,
        "payload_hash": _payload_hash(raw_bytes),
        "payload_bytes": len(raw_bytes),
        "payload_truncated": payload_truncated,
        "sanitized": True,
        "raw_payload": capture,
    }
