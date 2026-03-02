import hashlib
import json
import logging
import secrets
import time
from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple

import redis
from redis.exceptions import RedisError

from app.config.settings import settings

logger = logging.getLogger(__name__)


class SigningContextError(Exception):
    """Base exception for signing context errors."""


class SigningContextUnavailableError(SigningContextError):
    """Raised when Redis cannot be reached or queried."""


class SigningContextConflictError(SigningContextError):
    """Raised when an existing pending context conflicts with init request data."""

    def __init__(self, message: str, existing_context: Optional[Dict] = None):
        super().__init__(message)
        self.existing_context = existing_context or {}


class SigningContextStore:
    def __init__(
        self,
        host: str,
        port: int,
        db: int,
        ttl_seconds: int,
        key_prefix: str,
        connect_timeout_seconds: int,
        socket_timeout_seconds: int,
    ):
        self.ttl_seconds = ttl_seconds
        self.key_prefix = key_prefix
        self.client = redis.Redis(
            host=host,
            port=port,
            db=db,
            decode_responses=True,
            socket_connect_timeout=connect_timeout_seconds,
            socket_timeout=socket_timeout_seconds,
        )

    @staticmethod
    def build_pdf_sha256(pdf_b64: str) -> str:
        return hashlib.sha256(str(pdf_b64).encode("utf-8")).hexdigest()

    @staticmethod
    def build_request_fingerprint(
        id_doc: str,
        id_user: str,
        field_id: str,
        is_closing: bool,
        is_digital: bool,
        pdf_sha256: str,
    ) -> str:
        payload = {
            "id_doc": str(id_doc),
            "id_user": str(id_user),
            "field_id": str(field_id),
            "is_closing": bool(is_closing),
            "is_digital": bool(is_digital),
            "pdf_sha256": pdf_sha256,
        }
        normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    @staticmethod
    def generate_batch_id(doc_ids: Iterable[str], first_user: str) -> str:
        now_ms = int(time.time() * 1000)
        sorted_ids = ",".join(sorted(str(doc_id) for doc_id in doc_ids))
        nonce = secrets.token_hex(8)
        raw = f"{sorted_ids}|{first_user}|{now_ms}|{nonce}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _doc_key(self, doc_id: str) -> str:
        return f"{self.key_prefix}:doc:{doc_id}"

    @staticmethod
    def _parse_context(raw_context: Optional[str]) -> Optional[Dict]:
        if not raw_context:
            return None
        try:
            context = json.loads(raw_context)
            if not isinstance(context, dict):
                return None
            return context
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _build_context_payload(
        batch_id: str,
        id_doc: str,
        id_user: str,
        field_id: str,
        is_closing: bool,
        is_digital: bool,
        pdf_sha256: str,
        request_fingerprint: str,
    ) -> Dict:
        timestamp_ms = int(time.time() * 1000)
        datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return {
            "batch_id": batch_id,
            "id_doc": str(id_doc),
            "timestamp_ms": timestamp_ms,
            "datetimesigned": datetimesigned,
            "isclosing": bool(is_closing),
            "id_user": str(id_user),
            "field_id": str(field_id),
            "pdf_sha256": pdf_sha256,
            "request_fingerprint": request_fingerprint,
            "created_at_ms": timestamp_ms,
            "is_digital": bool(is_digital),
        }

    def create_or_get_init_context(
        self,
        *,
        batch_id: str,
        id_doc: str,
        id_user: str,
        field_id: str,
        is_closing: bool,
        is_digital: bool,
        pdf_b64: str,
    ) -> Tuple[Dict, str]:
        doc_key = self._doc_key(str(id_doc))
        pdf_sha256 = self.build_pdf_sha256(pdf_b64)
        request_fingerprint = self.build_request_fingerprint(
            id_doc=id_doc,
            id_user=id_user,
            field_id=field_id,
            is_closing=is_closing,
            is_digital=is_digital,
            pdf_sha256=pdf_sha256,
        )
        payload = self._build_context_payload(
            batch_id=batch_id,
            id_doc=id_doc,
            id_user=id_user,
            field_id=field_id,
            is_closing=is_closing,
            is_digital=is_digital,
            pdf_sha256=pdf_sha256,
            request_fingerprint=request_fingerprint,
        )
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        try:
            created = self.client.set(doc_key, payload_json, ex=self.ttl_seconds, nx=True)
            if created:
                return payload, "created"

            existing_raw = self.client.get(doc_key)
            existing_payload = self._parse_context(existing_raw)
            if not existing_payload:
                # Retry once in case key disappeared between NX and GET.
                created_after_race = self.client.set(doc_key, payload_json, ex=self.ttl_seconds, nx=True)
                if created_after_race:
                    return payload, "created"
                raise SigningContextUnavailableError(
                    f"Invalid or unreadable signing context for document {id_doc}"
                )

            if existing_payload.get("request_fingerprint") == request_fingerprint:
                self.client.expire(doc_key, self.ttl_seconds)
                return existing_payload, "hit"

            raise SigningContextConflictError(
                f"Pending signing context conflict for document {id_doc}",
                existing_context=existing_payload,
            )
        except SigningContextConflictError:
            raise
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while creating context for document {id_doc}: {exc}"
            ) from exc

    def get_context_for_end(self, doc_id: str) -> Optional[Dict]:
        doc_key = self._doc_key(str(doc_id))
        try:
            raw_context = self.client.get(doc_key)
            context = self._parse_context(raw_context)
            if not context:
                return None
            return context
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while retrieving context for document {doc_id}: {exc}"
            ) from exc

    def delete_context(self, doc_id: str) -> bool:
        doc_key = self._doc_key(str(doc_id))
        try:
            deleted = self.client.delete(doc_key)
            return bool(deleted)
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while deleting context for document {doc_id}: {exc}"
            ) from exc


signing_context_store = SigningContextStore(
    host=settings.REDIS_HOST,
    port=settings.REDIS_PORT,
    db=settings.REDIS_DB,
    ttl_seconds=settings.REDIS_TTL_SECONDS,
    key_prefix=settings.REDIS_KEY_PREFIX,
    connect_timeout_seconds=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
    socket_timeout_seconds=settings.REDIS_SOCKET_TIMEOUT_SECONDS,
)
