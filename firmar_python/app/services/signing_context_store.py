from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Optional, Tuple

import redis
from redis.exceptions import RedisError

from app.config.settings import settings

logger = logging.getLogger(__name__)

STATE_PENDING = "pending"
STATE_FINALIZING = "finalizing"
STATE_FINALIZED = "finalized"
CONTEXT_VERSION = 1


class SigningContextError(Exception):
    """Base exception for signing context errors."""


class SigningContextUnavailableError(SigningContextError):
    """Raised when Redis cannot be reached or queried."""


class SigningContextConflictError(SigningContextError):
    """Raised when an existing pending context conflicts with init request data."""

    def __init__(self, message: str, existing_context: Optional[Dict] = None):
        super().__init__(message)
        self.existing_context = existing_context or {}


@dataclass(frozen=True)
class SigningContextRecord:
    payload: Dict

    def to_dict(self) -> Dict:
        return dict(self.payload)


@dataclass(frozen=True)
class FinalizeClaimResult:
    result: str
    context: Dict
    lease_token: Optional[str] = None


@dataclass(frozen=True)
class EntityLock:
    redis_key: str
    token: str
    entity: str


class SigningContextStore:
    _CLAIM_SCRIPT = """
    local value = redis.call('GET', KEYS[1])
    if not value then
        return cjson.encode({result='missing'})
    end

    local ctx = cjson.decode(value)
    local expected_fingerprint = ARGV[1]
    local now_ms = tonumber(ARGV[2])
    local lease_ms = tonumber(ARGV[3])
    local ttl_ms = tonumber(ARGV[4])
    local lease_token = ARGV[5]

    if tostring(ctx['request_fingerprint']) ~= tostring(expected_fingerprint) then
        return cjson.encode({result='mismatch', context=ctx})
    end

    local state = tostring(ctx['state'] or 'pending')
    if state == 'pending' then
        ctx['state'] = 'finalizing'
        ctx['lease_token'] = lease_token
        ctx['lease_expires_at_ms'] = now_ms + lease_ms
        ctx['attempt_count'] = tonumber(ctx['attempt_count'] or 0) + 1
        redis.call('SET', KEYS[1], cjson.encode(ctx), 'PX', ttl_ms)
        return cjson.encode({result='claimed', context=ctx, lease_token=lease_token})
    end

    if state == 'finalizing' then
        local expires_at = tonumber(ctx['lease_expires_at_ms'] or 0)
        if expires_at <= now_ms then
            ctx['state'] = 'finalizing'
            ctx['lease_token'] = lease_token
            ctx['lease_expires_at_ms'] = now_ms + lease_ms
            ctx['attempt_count'] = tonumber(ctx['attempt_count'] or 0) + 1
            redis.call('SET', KEYS[1], cjson.encode(ctx), 'PX', ttl_ms)
            return cjson.encode({result='claimed', context=ctx, lease_token=lease_token})
        end
        return cjson.encode({result='busy', context=ctx})
    end

    return cjson.encode({result=state, context=ctx})
    """

    _RELEASE_SCRIPT = """
    local value = redis.call('GET', KEYS[1])
    if not value then
        return cjson.encode({result='missing'})
    end

    local ctx = cjson.decode(value)
    if tostring(ctx['lease_token'] or '') ~= tostring(ARGV[1]) then
        return cjson.encode({result='mismatch', context=ctx})
    end

    ctx['state'] = 'pending'
    ctx['lease_token'] = cjson.null
    ctx['lease_expires_at_ms'] = cjson.null
    ctx['last_error_code'] = ARGV[2]
    ctx['last_error_message'] = ARGV[3]
    redis.call('SET', KEYS[1], cjson.encode(ctx), 'PX', tonumber(ARGV[4]))
    return cjson.encode({result='released', context=ctx})
    """

    _COMPLETE_SCRIPT = """
    local value = redis.call('GET', KEYS[1])
    if not value then
        return cjson.encode({result='missing'})
    end

    local ctx = cjson.decode(value)
    if tostring(ctx['lease_token'] or '') ~= tostring(ARGV[1]) then
        return cjson.encode({result='mismatch', context=ctx})
    end

    ctx['state'] = 'finalized'
    ctx['lease_token'] = cjson.null
    ctx['lease_expires_at_ms'] = cjson.null
    ctx['last_error_code'] = cjson.null
    ctx['last_error_message'] = cjson.null
    redis.call('SET', KEYS[1], cjson.encode(ctx), 'PX', tonumber(ARGV[2]))
    return cjson.encode({result='finalized', context=ctx})
    """

    _RELEASE_LOCK_SCRIPT = """
    if redis.call('GET', KEYS[1]) == ARGV[1] then
        return redis.call('DEL', KEYS[1])
    end
    return 0
    """

    def __init__(
        self,
        host: str,
        port: int,
        db: int,
        ttl_seconds: int,
        key_prefix: str,
        connect_timeout_seconds: int,
        socket_timeout_seconds: int,
        finalize_lease_ms: int,
        entity_lock_ttl_ms: int,
        finalized_ttl_seconds: int,
    ):
        self.ttl_seconds = ttl_seconds
        self.ttl_ms = ttl_seconds * 1000
        self.key_prefix = key_prefix
        self.finalize_lease_ms = finalize_lease_ms
        self.entity_lock_ttl_ms = entity_lock_ttl_ms
        self.finalized_ttl_ms = finalized_ttl_seconds * 1000
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
    def build_json_sha256(json_b64: str) -> str:
        return hashlib.sha256(str(json_b64).encode("utf-8")).hexdigest()

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
    def build_jades_request_fingerprint(exp_id: str, id_user: Optional[str], json_sha256: str) -> str:
        payload = {
            "exp_id": str(exp_id),
            "id_user": str(id_user) if id_user is not None else None,
            "json_sha256": json_sha256,
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

    def _jades_key(self, exp_id: str) -> str:
        return f"{self.key_prefix}:jades:{exp_id}"

    def _lock_key(self, entity_type: str, entity_id: str) -> str:
        return f"{self.key_prefix}:lock:{entity_type}:{entity_id}"

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
    def _unwrap_eval_response(raw_response: Optional[str]) -> Dict:
        if not raw_response:
            return {"result": "missing"}
        try:
            payload = json.loads(raw_response)
        except (TypeError, ValueError):
            return {"result": "invalid"}
        return payload if isinstance(payload, dict) else {"result": "invalid"}

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
            "version": CONTEXT_VERSION,
            "state": STATE_PENDING,
            "batch_id": batch_id,
            "id_doc": str(id_doc),
            "id_user": str(id_user),
            "field_id": str(field_id),
            "isclosing": bool(is_closing),
            "is_digital": bool(is_digital),
            "pdf_sha256": pdf_sha256,
            "request_fingerprint": request_fingerprint,
            "timestamp_ms": timestamp_ms,
            "datetimesigned": datetimesigned,
            "created_at_ms": timestamp_ms,
            "attempt_count": 0,
            "lease_token": None,
            "lease_expires_at_ms": None,
            "last_error_code": None,
            "last_error_message": None,
        }

    @staticmethod
    def _build_jades_context_payload(
        exp_id: str,
        id_user: Optional[str],
        json_sha256: str,
        request_fingerprint: str,
    ) -> Dict:
        timestamp_ms = int(time.time() * 1000)
        datetimesigned = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        return {
            "version": CONTEXT_VERSION,
            "state": STATE_PENDING,
            "exp_id": str(exp_id),
            "id_user": str(id_user) if id_user is not None else None,
            "json_sha256": json_sha256,
            "request_fingerprint": request_fingerprint,
            "timestamp_ms": timestamp_ms,
            "datetimesigned": datetimesigned,
            "created_at_ms": timestamp_ms,
            "attempt_count": 0,
            "lease_token": None,
            "lease_expires_at_ms": None,
            "last_error_code": None,
            "last_error_message": None,
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
            created = self.client.set(doc_key, payload_json, px=self.ttl_ms, nx=True)
            if created:
                return payload, "created"

            existing_payload = self._parse_context(self.client.get(doc_key))
            if not existing_payload:
                recreated = self.client.set(doc_key, payload_json, px=self.ttl_ms, nx=True)
                if recreated:
                    return payload, "created"
                raise SigningContextUnavailableError(
                    f"Invalid or unreadable signing context for document {id_doc}"
                )

            if existing_payload.get("request_fingerprint") == request_fingerprint:
                self.client.pexpire(doc_key, self.ttl_ms)
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

    def claim_context_for_end(self, doc_id: str, request_fingerprint: str) -> FinalizeClaimResult:
        return self._claim_context(
            redis_key=self._doc_key(str(doc_id)),
            request_fingerprint=request_fingerprint,
            entity=f"document {doc_id}",
        )

    def create_or_get_jades_context(self, exp_id: str, id_user: Optional[str], json_b64: str) -> Tuple[Dict, str]:
        jades_key = self._jades_key(str(exp_id))
        json_sha256 = self.build_json_sha256(json_b64)
        request_fingerprint = self.build_jades_request_fingerprint(exp_id, id_user, json_sha256)
        payload = self._build_jades_context_payload(
            exp_id=exp_id,
            id_user=id_user,
            json_sha256=json_sha256,
            request_fingerprint=request_fingerprint,
        )
        payload_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))

        try:
            created = self.client.set(jades_key, payload_json, px=self.ttl_ms, nx=True)
            if created:
                return payload, "created"

            existing_payload = self._parse_context(self.client.get(jades_key))
            if not existing_payload:
                recreated = self.client.set(jades_key, payload_json, px=self.ttl_ms, nx=True)
                if recreated:
                    return payload, "created"
                raise SigningContextUnavailableError(
                    f"Invalid or unreadable JADES signing context for expediente {exp_id}"
                )

            if existing_payload.get("request_fingerprint") == request_fingerprint:
                self.client.pexpire(jades_key, self.ttl_ms)
                return existing_payload, "hit"

            raise SigningContextConflictError(
                f"Pending JADES signing context conflict for expediente {exp_id}",
                existing_context=existing_payload,
            )
        except SigningContextConflictError:
            raise
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while creating JADES context for expediente {exp_id}: {exc}"
            ) from exc

    def claim_jades_context(self, exp_id: str, request_fingerprint: str) -> FinalizeClaimResult:
        return self._claim_context(
            redis_key=self._jades_key(str(exp_id)),
            request_fingerprint=request_fingerprint,
            entity=f"expediente {exp_id}",
        )

    def _claim_context(self, *, redis_key: str, request_fingerprint: str, entity: str) -> FinalizeClaimResult:
        now_ms = int(time.time() * 1000)
        lease_token = secrets.token_hex(16)
        try:
            raw_response = self.client.eval(
                self._CLAIM_SCRIPT,
                1,
                redis_key,
                request_fingerprint,
                now_ms,
                self.finalize_lease_ms,
                self.ttl_ms,
                lease_token,
            )
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while claiming context for {entity}: {exc}"
            ) from exc

        payload = self._unwrap_eval_response(raw_response)
        return FinalizeClaimResult(
            result=str(payload.get("result", "invalid")),
            context=payload.get("context") or {},
            lease_token=payload.get("lease_token"),
        )

    def release_context_for_retry(
        self,
        doc_id: str,
        lease_token: str,
        *,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> str:
        return self._release_context(
            redis_key=self._doc_key(str(doc_id)),
            lease_token=lease_token,
            entity=f"document {doc_id}",
            error_code=error_code,
            error_message=error_message,
        )

    def release_jades_context_for_retry(
        self,
        exp_id: str,
        lease_token: str,
        *,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> str:
        return self._release_context(
            redis_key=self._jades_key(str(exp_id)),
            lease_token=lease_token,
            entity=f"expediente {exp_id}",
            error_code=error_code,
            error_message=error_message,
        )

    def _release_context(
        self,
        *,
        redis_key: str,
        lease_token: str,
        entity: str,
        error_code: Optional[str],
        error_message: Optional[str],
    ) -> str:
        try:
            raw_response = self.client.eval(
                self._RELEASE_SCRIPT,
                1,
                redis_key,
                lease_token,
                error_code or "",
                error_message or "",
                self.ttl_ms,
            )
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while releasing context for {entity}: {exc}"
            ) from exc

        payload = self._unwrap_eval_response(raw_response)
        return str(payload.get("result", "invalid"))

    def complete_context_finalize(self, doc_id: str, lease_token: str) -> str:
        return self._complete_context(
            redis_key=self._doc_key(str(doc_id)),
            lease_token=lease_token,
            entity=f"document {doc_id}",
        )

    def complete_jades_context_finalize(self, exp_id: str, lease_token: str) -> str:
        return self._complete_context(
            redis_key=self._jades_key(str(exp_id)),
            lease_token=lease_token,
            entity=f"expediente {exp_id}",
        )

    def _complete_context(self, *, redis_key: str, lease_token: str, entity: str) -> str:
        try:
            raw_response = self.client.eval(
                self._COMPLETE_SCRIPT,
                1,
                redis_key,
                lease_token,
                self.finalized_ttl_ms,
            )
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while completing context for {entity}: {exc}"
            ) from exc

        payload = self._unwrap_eval_response(raw_response)
        return str(payload.get("result", "invalid"))

    def acquire_entity_lock(self, entity_type: str, entity_id: str) -> Optional[EntityLock]:
        redis_key = self._lock_key(entity_type, entity_id)
        token = secrets.token_hex(16)
        try:
            acquired = self.client.set(redis_key, token, px=self.entity_lock_ttl_ms, nx=True)
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while acquiring {entity_type} lock for {entity_id}: {exc}"
            ) from exc

        if not acquired:
            return None
        return EntityLock(redis_key=redis_key, token=token, entity=f"{entity_type} {entity_id}")

    def release_entity_lock(self, lock: EntityLock) -> bool:
        try:
            released = self.client.eval(self._RELEASE_LOCK_SCRIPT, 1, lock.redis_key, lock.token)
        except RedisError as exc:
            raise SigningContextUnavailableError(
                f"Redis unavailable while releasing {lock.entity} lock: {exc}"
            ) from exc
        return bool(released)

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
    finalize_lease_ms=settings.SIGNING_FINALIZE_LEASE_MS,
    entity_lock_ttl_ms=settings.SIGNING_ENTITY_LOCK_TTL_MS,
    finalized_ttl_seconds=settings.REDIS_FINALIZED_TTL_SECONDS,
)
