from __future__ import annotations

import base64
import gzip
import logging
import os
import time
import uuid
import json
import queue
import socket
import threading
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from app.config.settings import settings

try:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError:  # pragma: no cover - local test environments may not have cryptography installed
    AESGCM = None  # type: ignore[assignment]

try:
    from psycopg2 import Binary
    from psycopg2 import pool as pg_pool
    from psycopg2.extras import Json
except ImportError:  # pragma: no cover - local test environments may not have psycopg2 installed
    Binary = lambda value: value  # type: ignore[assignment]
    pg_pool = None

    class Json:  # type: ignore[no-redef]
        def __init__(self, value):
            self.adapted = value

from .constants import (
    ENTRY_APP_LOG,
    OPERATION_FAILED,
    OPERATION_PARTIAL_ERROR,
    OPERATION_RUNNING,
    STAGE_ERROR,
    STAGE_RUNNING,
    STAGE_SUCCESS,
    SUBJECT_ERROR,
    SUBJECT_RUNNING,
    SUBJECT_SUCCESS,
)
from .context import (
    bind_stage,
    bind_subject,
    get_current_operation_error,
    get_current_operation_id,
    get_current_operation_status,
    get_current_stage_id,
    get_current_subject_id,
    reset_bindings,
    set_current_operation_status,
    suppress_logging,
)
from .sanitizer import sanitize_payload

logger = logging.getLogger(__name__)

_SERVICE_NAME = "firmador-python"
_INSTANCE_ID = f"{socket.gethostname()}:{os.getpid()}"
_pool = None
_entry_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue(maxsize=settings.OBS_ASYNC_QUEUE_SIZE)
_entry_worker_started = False
_runtime_worker_started = False
_entry_worker_lock = threading.Lock()
_runtime_worker_lock = threading.Lock()
_dropped_app_logs = 0
_last_queue_error_log = 0.0
_last_flush_at: datetime | None = None
_payload_vault_key: bytes | None | object = object()


def _get_pool():
    global _pool
    if _pool is not None:
        return _pool
    if pg_pool is None:
        return None

    try:
        _pool = pg_pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=6,
            host=os.getenv("OBS_DB_HOST", "obs-postgres"),
            port=int(os.getenv("OBS_DB_PORT", "5432")),
            dbname=os.getenv("OBS_DB_NAME", "obs_dashboard"),
            user=os.getenv("OBS_DB_USER", "obs_user"),
            password=os.getenv("OBS_DB_PASSWORD", "obs_password"),
            connect_timeout=3,
        )
    except Exception:
        with suppress_logging():
            logger.exception("observability recorder pool init failed")
    return _pool


@contextmanager
def _conn():
    pool = _get_pool()
    if pool is None:
        yield None
        return

    conn = None
    try:
        conn = pool.getconn()
        yield conn
        conn.commit()
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            pool.putconn(conn)


def generate_operation_id() -> str:
    return str(uuid.uuid4())


def _json(value: Optional[Dict[str, Any]]) -> Json:
    return Json(value or {})


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _coerce_timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _get_payload_vault_key() -> bytes | None:
    global _payload_vault_key
    if isinstance(_payload_vault_key, bytes):
        return _payload_vault_key
    if _payload_vault_key is None:
        return None

    raw_value = settings.OBS_PAYLOAD_VAULT_KEY
    if not raw_value or AESGCM is None:
        _payload_vault_key = None
        return None

    try:
        decoded = base64.b64decode(raw_value)
    except Exception:
        decoded = b""

    if len(decoded) != 32:
        with suppress_logging():
            logger.error("OBS_PAYLOAD_VAULT_KEY must be a base64-encoded 32-byte key")
        _payload_vault_key = None
        return None

    _payload_vault_key = decoded
    return decoded


def _write_runtime_status() -> None:
    try:
        from app.utils.saving import repair_backlog_size
    except Exception:
        repair_backlog_size = lambda: 0  # type: ignore[assignment]

    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO observability.runtime_status (
                    service_name, instance_id, queue_depth, dropped_events, last_flush_at, updated_at, attrs
                )
                VALUES (%s, %s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (service_name)
                DO UPDATE SET
                    instance_id = EXCLUDED.instance_id,
                    queue_depth = EXCLUDED.queue_depth,
                    dropped_events = EXCLUDED.dropped_events,
                    last_flush_at = EXCLUDED.last_flush_at,
                    updated_at = NOW(),
                    attrs = EXCLUDED.attrs
                """,
                (
                    _SERVICE_NAME,
                    _INSTANCE_ID,
                    _entry_queue.qsize(),
                    _dropped_app_logs,
                    _last_flush_at,
                    _json(
                        {
                            "queue_capacity": settings.OBS_ASYNC_QUEUE_SIZE,
                            "worker_alive": _entry_worker_started,
                            "payload_vault_enabled": bool(_get_payload_vault_key()),
                            "repair_backlog_size": repair_backlog_size(),
                        }
                    ),
                ),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("runtime status heartbeat failed")


def _runtime_worker_loop() -> None:
    interval = max(1, settings.OBS_RUNTIME_HEARTBEAT_SECONDS)
    while True:
        _write_runtime_status()
        time.sleep(interval)


def _insert_payload_vault(cur, item: Dict[str, Any], *, entry_id: int, occurred_at: datetime) -> int | None:
    payload = item.get("raw_payload")
    if not payload:
        return None

    key = _get_payload_vault_key()
    if not key:
        return None

    compressed = gzip.compress(payload["bytes"])
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, compressed, None)
    expires_at = _utcnow() + timedelta(days=settings.OBS_PAYLOAD_VAULT_RETENTION_DAYS)
    vault_attrs = {
        "entry_id": entry_id,
        "entry_occurred_at": occurred_at.isoformat(),
        **(item.get("raw_payload_attrs") or {}),
    }
    cur.execute(
        """
        INSERT INTO observability.payload_vault (
            operation_id, subject_id, stage_id, entry_kind, route, stage_key, payload_hash,
            content_kind, ciphertext, nonce, algorithm, compression, raw_bytes, stored_bytes,
            truncated, created_at, expires_at, attrs
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING vault_id
        """,
        (
            item["operation_id"],
            item["subject_id"],
            item["stage_id"],
            item["entry_kind"],
            item["route"],
            item.get("stage_key"),
            payload["payload_hash"],
            payload["content_kind"],
            Binary(ciphertext),
            Binary(nonce),
            "aes-256-gcm",
            "gzip",
            payload["raw_bytes"],
            len(ciphertext),
            payload["truncated"],
            occurred_at,
            expires_at,
            _json(vault_attrs),
        ),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def _record_entry_db(batch: list[Dict[str, Any]]) -> None:
    global _last_flush_at
    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            for item in batch:
                cur.execute(
                    """
                    INSERT INTO observability.stage_entry (
                        operation_id, subject_id, stage_id, entry_kind, log_level, logger_name,
                        title, message, payload_json, payload_text, payload_hash, payload_bytes,
                        payload_truncated, sanitized, http_method, url, route, status_code,
                        error_code, error_class, stacktrace, attrs
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING entry_id, occurred_at
                    """,
                    (
                        item["operation_id"],
                        item["subject_id"],
                        item["stage_id"],
                        item["entry_kind"],
                        item["log_level"],
                        item["logger_name"],
                        item["title"],
                        item["message"],
                        Json(item["payload_json"]) if item["payload_json"] is not None else None,
                        item["payload_text"],
                        item["payload_hash"],
                        item["payload_bytes"],
                        item["payload_truncated"],
                        item["sanitized"],
                        item["http_method"],
                        item["url"],
                        item["route"],
                        item["status_code"],
                        item["error_code"],
                        item["error_class"],
                        item["stacktrace"],
                        _json(item["attrs"]),
                    ),
                )
                row = cur.fetchone()
                if row:
                    entry_id = int(row[0])
                    occurred_at = _coerce_timestamp(row[1]) or _utcnow()
                    vault_id = _insert_payload_vault(cur, item, entry_id=entry_id, occurred_at=occurred_at)
                    if vault_id is not None:
                        cur.execute(
                            """
                            UPDATE observability.stage_entry
                            SET attrs = COALESCE(attrs, '{}'::jsonb) || %s::jsonb
                            WHERE occurred_at = %s AND entry_id = %s
                            """,
                            (
                                json.dumps(
                                    {
                                        "raw_payload_id": vault_id,
                                        "raw_payload_available": True,
                                        "raw_payload_truncated": bool(item["raw_payload"]["truncated"]),
                                    }
                                ),
                                occurred_at,
                                entry_id,
                            ),
                        )
            cur.close()
            _last_flush_at = _utcnow()
    except Exception:
        with suppress_logging():
            logger.exception("record_entry batch failed")


def _entry_worker_loop() -> None:
    flush_interval = max(0.01, settings.OBS_ASYNC_FLUSH_MS / 1000.0)
    batch_size = max(1, settings.OBS_ASYNC_BATCH_SIZE)

    while True:
        try:
            first_item = _entry_queue.get(timeout=flush_interval)
        except queue.Empty:
            continue

        batch = [first_item]
        deadline = time.monotonic() + flush_interval
        while len(batch) < batch_size:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            try:
                batch.append(_entry_queue.get(timeout=remaining))
            except queue.Empty:
                break

        _record_entry_db(batch)
        for _ in batch:
            _entry_queue.task_done()


def _ensure_entry_worker() -> None:
    global _entry_worker_started, _runtime_worker_started
    if not _entry_worker_started:
        with _entry_worker_lock:
            if not _entry_worker_started:
                worker = threading.Thread(
                    target=_entry_worker_loop,
                    name="observability-entry-writer",
                    daemon=True,
                )
                worker.start()
                _entry_worker_started = True

    if not _runtime_worker_started:
        with _runtime_worker_lock:
            if not _runtime_worker_started:
                worker = threading.Thread(
                    target=_runtime_worker_loop,
                    name="observability-runtime-heartbeat",
                    daemon=True,
                )
                worker.start()
                _runtime_worker_started = True


def start_operation(
    *,
    operation_key: str,
    route: str,
    method: str,
    client_ip: Optional[str] = None,
    id_user: Optional[str] = None,
    batch_size: int = 1,
    request_content_type: Optional[str] = None,
    request_size_bytes: Optional[int] = None,
    attrs: Optional[Dict[str, Any]] = None,
    operation_id: Optional[str] = None,
) -> str:
    operation_id = operation_id or generate_operation_id()
    try:
        with _conn() as conn:
            if conn is None:
                return operation_id
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO observability.operation_run (
                    operation_id, operation_key, route, method, client_ip, id_user,
                    batch_size, request_content_type, request_size_bytes, operation_status,
                    started_at, attrs
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                """,
                (
                    operation_id,
                    operation_key,
                    route,
                    method,
                    client_ip,
                    id_user,
                    batch_size,
                    request_content_type,
                    request_size_bytes,
                    OPERATION_RUNNING,
                    _json(attrs),
                ),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("start_operation failed")

    set_current_operation_status(OPERATION_RUNNING)
    _ensure_entry_worker()
    return operation_id


def update_operation(
    operation_id: Optional[str] = None,
    *,
    batch_size: Optional[int] = None,
    id_user: Optional[str] = None,
    http_status_code: Optional[int] = None,
    operation_status: Optional[str] = None,
    request_content_type: Optional[str] = None,
    request_size_bytes: Optional[int] = None,
    response_content_type: Optional[str] = None,
    response_size_bytes: Optional[int] = None,
    error_message: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> None:
    operation_id = operation_id or get_current_operation_id()
    if not operation_id:
        return

    assignments = []
    params: list[Any] = []

    for column, value in (
        ("batch_size", batch_size),
        ("id_user", id_user),
        ("http_status_code", http_status_code),
        ("request_content_type", request_content_type),
        ("request_size_bytes", request_size_bytes),
        ("response_content_type", response_content_type),
        ("response_size_bytes", response_size_bytes),
        ("error_message", error_message),
    ):
        if value is not None:
            assignments.append(f"{column} = %s")
            params.append(value)

    if operation_status is not None:
        assignments.append("operation_status = %s")
        params.append(operation_status)
        set_current_operation_status(operation_status, error_message)
    elif error_message is not None:
        set_current_operation_status(get_current_operation_status(), error_message)

    if attrs:
        assignments.append("attrs = COALESCE(attrs, '{}'::jsonb) || %s::jsonb")
        params.append(json.dumps(attrs))

    if not assignments:
        return

    params.append(operation_id)

    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                f"UPDATE observability.operation_run SET {', '.join(assignments)} WHERE operation_id = %s",
                params,
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("update_operation failed")


def finish_operation(
    operation_id: Optional[str] = None,
    *,
    status: Optional[str] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    operation_id = operation_id or get_current_operation_id()
    if not operation_id:
        return

    resolved_status = status or get_current_operation_status() or OPERATION_RUNNING
    resolved_error = error_message if error_message is not None else get_current_operation_error()

    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE observability.operation_run
                SET finished_at = NOW(),
                    duration_ms = COALESCE(%s, GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000))::INT),
                    operation_status = %s,
                    error_message = %s
                WHERE operation_id = %s
                """,
                (duration_ms, resolved_status, resolved_error, operation_id),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("finish_operation failed")


def upsert_subject(
    *,
    subject_type: str,
    subject_key: str,
    display_name: Optional[str] = None,
    id_user: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
    operation_id: Optional[str] = None,
    parent_subject_id: Optional[int] = None,
) -> Optional[int]:
    operation_id = operation_id or get_current_operation_id()
    if not operation_id:
        return None

    parent_subject_id = parent_subject_id if parent_subject_id is not None else get_current_subject_id()

    try:
        with _conn() as conn:
            if conn is None:
                return None
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO observability.operation_subject (
                    operation_id, parent_subject_id, subject_type, subject_key,
                    display_name, id_user, subject_status, started_at, attrs
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                ON CONFLICT (operation_id, subject_type, subject_key)
                DO UPDATE SET
                    parent_subject_id = COALESCE(EXCLUDED.parent_subject_id, observability.operation_subject.parent_subject_id),
                    display_name = COALESCE(EXCLUDED.display_name, observability.operation_subject.display_name),
                    id_user = COALESCE(EXCLUDED.id_user, observability.operation_subject.id_user),
                    attrs = COALESCE(observability.operation_subject.attrs, '{}'::jsonb) || COALESCE(EXCLUDED.attrs, '{}'::jsonb)
                RETURNING subject_id
                """,
                (
                    operation_id,
                    parent_subject_id,
                    subject_type,
                    subject_key,
                    display_name,
                    id_user,
                    SUBJECT_RUNNING,
                    _json(attrs),
                ),
            )
            row = cur.fetchone()
            cur.close()
            return int(row[0]) if row else None
    except Exception:
        with suppress_logging():
            logger.exception("upsert_subject failed")
    return None


def finish_subject(
    subject_id: Optional[int] = None,
    *,
    status: str = SUBJECT_SUCCESS,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> None:
    subject_id = subject_id or get_current_subject_id()
    if not subject_id:
        return

    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE observability.operation_subject
                SET finished_at = NOW(),
                    duration_ms = COALESCE(%s, GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000))::INT),
                    subject_status = %s,
                    error_message = %s,
                    attrs = COALESCE(attrs, '{}'::jsonb) || %s
                WHERE subject_id = %s
                """,
                (duration_ms, status, error_message, _json(attrs), subject_id),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("finish_subject failed")


def start_stage(
    *,
    stage_key: str,
    stage_label: Optional[str] = None,
    subject_id: Optional[int] = None,
    parent_stage_id: Optional[int] = None,
    attrs: Optional[Dict[str, Any]] = None,
    operation_id: Optional[str] = None,
) -> Optional[int]:
    operation_id = operation_id or get_current_operation_id()
    if not operation_id:
        return None

    subject_id = subject_id if subject_id is not None else get_current_subject_id()
    parent_stage_id = parent_stage_id if parent_stage_id is not None else get_current_stage_id()

    try:
        with _conn() as conn:
            if conn is None:
                return None
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO observability.stage_run (
                    operation_id, subject_id, parent_stage_id, stage_key, stage_label,
                    stage_status, started_at, attrs
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                RETURNING stage_id
                """,
                (
                    operation_id,
                    subject_id,
                    parent_stage_id,
                    stage_key,
                    stage_label or stage_key,
                    STAGE_RUNNING,
                    _json(attrs),
                ),
            )
            row = cur.fetchone()
            cur.close()
            return int(row[0]) if row else None
    except Exception:
        with suppress_logging():
            logger.exception("start_stage failed")
    return None


def finish_stage(
    stage_id: Optional[int] = None,
    *,
    status: str = STAGE_SUCCESS,
    error_message: Optional[str] = None,
    error_class: Optional[str] = None,
    duration_ms: Optional[int] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> None:
    stage_id = stage_id or get_current_stage_id()
    if not stage_id:
        return

    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE observability.stage_run
                SET finished_at = NOW(),
                    duration_ms = COALESCE(%s, GREATEST(0, FLOOR(EXTRACT(EPOCH FROM (NOW() - started_at)) * 1000))::INT),
                    stage_status = %s,
                    error_message = %s,
                    error_class = %s,
                    attrs = COALESCE(attrs, '{}'::jsonb) || %s
                WHERE stage_id = %s
                """,
                (duration_ms, status, error_message, error_class, _json(attrs), stage_id),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("finish_stage failed")


def upsert_repair_manifest(
    *,
    operation_id: Optional[str],
    id_doc: Optional[str],
    manifest_path: str,
    target_path: str,
    temp_path: str,
    hash_doc: str,
    payload_sha256: str,
    bytes_written: Optional[int],
    retryable: bool = True,
    db_committed: bool = False,
    attrs: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO observability.repair_manifest (
                    operation_id, id_doc, manifest_path, target_path, temp_path, hash_doc,
                    payload_sha256, bytes_written, status, retryable, db_committed, attrs
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s, %s, %s)
                ON CONFLICT (manifest_path)
                DO UPDATE SET
                    operation_id = EXCLUDED.operation_id,
                    id_doc = EXCLUDED.id_doc,
                    target_path = EXCLUDED.target_path,
                    temp_path = EXCLUDED.temp_path,
                    hash_doc = EXCLUDED.hash_doc,
                    payload_sha256 = EXCLUDED.payload_sha256,
                    bytes_written = EXCLUDED.bytes_written,
                    status = 'pending',
                    retryable = EXCLUDED.retryable,
                    db_committed = EXCLUDED.db_committed,
                    attrs = COALESCE(observability.repair_manifest.attrs, '{}'::jsonb) || COALESCE(EXCLUDED.attrs, '{}'::jsonb),
                    last_error = NULL,
                    recovered_at = NULL
                """,
                (
                    operation_id,
                    id_doc,
                    manifest_path,
                    target_path,
                    temp_path,
                    hash_doc,
                    payload_sha256,
                    bytes_written,
                    retryable,
                    db_committed,
                    _json(attrs),
                ),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("upsert_repair_manifest failed")


def update_repair_manifest_status(
    manifest_path: str,
    *,
    status: str,
    last_error: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> None:
    try:
        with _conn() as conn:
            if conn is None:
                return
            cur = conn.cursor()
            cur.execute(
                """
                UPDATE observability.repair_manifest
                SET status = %s,
                    last_error = %s,
                    recovered_at = CASE WHEN %s = 'recovered' THEN NOW() ELSE recovered_at END,
                    attrs = COALESCE(attrs, '{}'::jsonb) || %s
                WHERE manifest_path = %s
                """,
                (status, last_error, status, _json(attrs), manifest_path),
            )
            cur.close()
    except Exception:
        with suppress_logging():
            logger.exception("update_repair_manifest_status failed")


def record_entry(
    *,
    entry_kind: str,
    title: Optional[str] = None,
    message: Optional[str] = None,
    payload: Any = None,
    raw_payload: Any = None,
    capture_raw_payload: bool = False,
    payload_content_kind: Optional[str] = None,
    raw_payload_attrs: Optional[Dict[str, Any]] = None,
    operation_id: Optional[str] = None,
    subject_id: Optional[int] = None,
    stage_id: Optional[int] = None,
    log_level: Optional[str] = None,
    logger_name: Optional[str] = None,
    http_method: Optional[str] = None,
    url: Optional[str] = None,
    route: Optional[str] = None,
    status_code: Optional[int] = None,
    error_code: Optional[str] = None,
    error_class: Optional[str] = None,
    stacktrace: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> None:
    operation_id = operation_id or get_current_operation_id()
    if not operation_id:
        return

    subject_id = subject_id if subject_id is not None else get_current_subject_id()
    stage_id = stage_id if stage_id is not None else get_current_stage_id()
    payload_info = sanitize_payload(
        payload,
        capture_raw=capture_raw_payload,
        raw_payload=raw_payload,
        content_kind=payload_content_kind,
        max_raw_bytes=settings.OBS_PAYLOAD_VAULT_MAX_BYTES,
    )
    entry = {
        "operation_id": operation_id,
        "subject_id": subject_id,
        "stage_id": stage_id,
        "entry_kind": entry_kind,
        "log_level": log_level,
        "logger_name": logger_name,
        "title": title,
        "message": message,
        "payload_json": payload_info["payload_json"],
        "payload_text": payload_info["payload_text"],
        "payload_hash": payload_info["payload_hash"],
        "payload_bytes": payload_info["payload_bytes"],
        "payload_truncated": payload_info["payload_truncated"],
        "sanitized": payload_info["sanitized"],
        "raw_payload": payload_info["raw_payload"],
        "raw_payload_attrs": raw_payload_attrs or {},
        "http_method": http_method,
        "url": url,
        "route": route,
        "status_code": status_code,
        "error_code": error_code,
        "error_class": error_class,
        "stacktrace": stacktrace,
        "attrs": attrs or {},
    }

    _ensure_entry_worker()

    global _dropped_app_logs, _last_queue_error_log
    try:
        _entry_queue.put_nowait(entry)
    except queue.Full:
        if entry_kind == ENTRY_APP_LOG:
            _dropped_app_logs += 1
            now = time.monotonic()
            if now - _last_queue_error_log >= 30:
                _last_queue_error_log = now
                with suppress_logging():
                    logger.error("observability queue full; dropping app_log entries")
            return
        _record_entry_db([entry])


def mark_operation_partial_error(error_message: Optional[str] = None) -> None:
    update_operation(operation_status=OPERATION_PARTIAL_ERROR, error_message=error_message)


def mark_operation_failed(error_message: Optional[str] = None) -> None:
    update_operation(operation_status=OPERATION_FAILED, error_message=error_message)


@dataclass
class SubjectScope:
    subject_type: str
    subject_key: str
    display_name: Optional[str] = None
    id_user: Optional[str] = None
    attrs: Optional[Dict[str, Any]] = None
    _subject_id: Optional[int] = None
    _tokens: Optional[Dict[str, Any]] = None
    _status: str = SUBJECT_SUCCESS
    _error_message: Optional[str] = None
    _attrs_update: Dict[str, Any] | None = None
    _t0: float = 0.0

    def __enter__(self):
        self._t0 = time.monotonic()
        self._subject_id = upsert_subject(
            subject_type=self.subject_type,
            subject_key=self.subject_key,
            display_name=self.display_name,
            id_user=self.id_user,
            attrs=self.attrs,
        )
        self._tokens = bind_subject(self._subject_id)
        return self

    def set_status(self, status: str, *, error_message: Optional[str] = None, attrs: Optional[Dict[str, Any]] = None) -> None:
        self._status = status
        if error_message is not None:
            self._error_message = error_message
        if attrs:
            self._attrs_update = attrs

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.monotonic() - self._t0) * 1000) if self._t0 else None
        if exc_type is not None:
            finish_subject(
                self._subject_id,
                status=SUBJECT_ERROR,
                error_message=str(exc_val)[:500],
                duration_ms=duration_ms,
                attrs=self._attrs_update,
            )
        else:
            finish_subject(
                self._subject_id,
                status=self._status,
                error_message=self._error_message,
                duration_ms=duration_ms,
                attrs=self._attrs_update,
            )
        if self._tokens:
            reset_bindings(self._tokens)
        return False


@dataclass
class StageScope:
    stage_key: str
    stage_label: Optional[str] = None
    attrs: Optional[Dict[str, Any]] = None
    _stage_id: Optional[int] = None
    _tokens: Optional[Dict[str, Any]] = None
    _status: str = STAGE_SUCCESS
    _error_message: Optional[str] = None
    _error_class: Optional[str] = None
    _attrs_update: Dict[str, Any] | None = None
    _t0: float = 0.0

    def __enter__(self):
        self._t0 = time.monotonic()
        self._stage_id = start_stage(
            stage_key=self.stage_key,
            stage_label=self.stage_label,
            attrs=self.attrs,
        )
        self._tokens = bind_stage(self._stage_id)
        return self

    def set_status(
        self,
        status: str,
        *,
        error_message: Optional[str] = None,
        error_class: Optional[str] = None,
        attrs: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._status = status
        if error_message is not None:
            self._error_message = error_message
        if error_class is not None:
            self._error_class = error_class
        if attrs:
            self._attrs_update = attrs

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.monotonic() - self._t0) * 1000) if self._t0 else None
        if exc_type is not None:
            finish_stage(
                self._stage_id,
                status=STAGE_ERROR,
                error_message=str(exc_val)[:500],
                error_class=exc_type.__name__,
                duration_ms=duration_ms,
                attrs=self._attrs_update,
            )
        else:
            finish_stage(
                self._stage_id,
                status=self._status,
                error_message=self._error_message,
                error_class=self._error_class,
                duration_ms=duration_ms,
                attrs=self._attrs_update,
            )
        if self._tokens:
            reset_bindings(self._tokens)
        return False


def subject_scope(
    subject_type: str,
    subject_key: str,
    *,
    display_name: Optional[str] = None,
    id_user: Optional[str] = None,
    attrs: Optional[Dict[str, Any]] = None,
) -> SubjectScope:
    return SubjectScope(subject_type, subject_key, display_name=display_name, id_user=id_user, attrs=attrs)


def stage_scope(
    stage_key: str,
    stage_label: Optional[str] = None,
    *,
    attrs: Optional[Dict[str, Any]] = None,
) -> StageScope:
    return StageScope(stage_key, stage_label=stage_label, attrs=attrs)
