from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Dict, Optional, Protocol, Tuple

from app.services.signing_context_store import signing_context_store

STATE_PENDING = "pending"
STATE_FINALIZING = "finalizing"
STATE_FINALIZED = "finalized"


@dataclass(frozen=True)
class ExternoClaim:
    result: str
    context: Dict
    lease_token: Optional[str] = None


def build_pdf_sha256(pdf_b64: str) -> str:
    return hashlib.sha256(str(pdf_b64).encode("utf-8")).hexdigest()


def build_externo_fingerprint(id_documento, id_firmante, ancla, pdf_b64: str) -> str:
    payload = {
        "id_documento": str(id_documento),
        "id_firmante": str(id_firmante),
        "ancla": str(ancla),
        "pdf_sha256": build_pdf_sha256(pdf_b64),
    }
    normalized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class _StoreBackend(Protocol):
    def set_nx(self, key: str, value: str, ttl_ms: int) -> bool: ...
    def get(self, key: str) -> Optional[str]: ...
    def set(self, key: str, value: str, ttl_ms: int) -> None: ...
    def delete(self, key: str) -> None: ...


class _MemoryBackend:
    def __init__(self):
        self._values: Dict[str, str] = {}

    def set_nx(self, key: str, value: str, ttl_ms: int) -> bool:
        if key in self._values:
            return False
        self._values[key] = value
        return True

    def get(self, key: str) -> Optional[str]:
        return self._values.get(key)

    def set(self, key: str, value: str, ttl_ms: int) -> None:
        self._values[key] = value

    def delete(self, key: str) -> None:
        self._values.pop(key, None)


class _RedisBackend:
    def __init__(self, client):
        self.client = client

    def set_nx(self, key: str, value: str, ttl_ms: int) -> bool:
        return bool(self.client.set(key, value, px=ttl_ms, nx=True))

    def get(self, key: str) -> Optional[str]:
        return self.client.get(key)

    def set(self, key: str, value: str, ttl_ms: int) -> None:
        self.client.set(key, value, px=ttl_ms)

    def delete(self, key: str) -> None:
        self.client.delete(key)


def _redis_client():
    client = getattr(signing_context_store, "client", None)
    if client is None:
        return None
    if not callable(getattr(client, "set", None)) or not callable(getattr(client, "get", None)):
        return None
    return client


class ExternoContextStore:
    def __init__(self, backend: _StoreBackend, *, key_prefix="signctx", ttl_ms=21600000, lock_ttl_ms=120000, finalized_ttl_ms=300000):
        self.backend = backend
        self.key_prefix = key_prefix
        self.ttl_ms = ttl_ms
        self.lock_ttl_ms = lock_ttl_ms
        self.finalized_ttl_ms = finalized_ttl_ms

    def _lock_key(self, entity_id: str) -> str:
        return f"{self.key_prefix}:externo:lock:{entity_id}"

    def _ctx_key(self, fingerprint: str) -> str:
        return f"{self.key_prefix}:externo:ctx:{fingerprint}"

    def acquire_lock(self, entity_id: str) -> Optional[str]:
        token = secrets.token_hex(16)
        if not self.backend.set_nx(self._lock_key(entity_id), token, self.lock_ttl_ms):
            return None
        return token

    def release_lock(self, entity_id: str, token: Optional[str]) -> None:
        if not token or not entity_id:
            return
        key = self._lock_key(entity_id)
        if self.backend.get(key) == token:
            self.backend.delete(key)

    def create_or_get_digital(
        self,
        fingerprint: str,
        timestamp_ms: int,
        datetimesigned: str,
    ) -> Tuple[Dict, str]:
        payload = {
            "state": STATE_PENDING,
            "request_fingerprint": fingerprint,
            "timestamp_ms": int(timestamp_ms),
            "datetimesigned": datetimesigned,
            "lease_token": None,
        }
        key = self._ctx_key(fingerprint)
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if self.backend.set_nx(key, encoded, self.ttl_ms):
            return payload, "created"
        existing = self._parse(self.backend.get(key))
        if existing:
            return existing, "hit"
        self.backend.set_nx(key, encoded, self.ttl_ms)
        return payload, "created"

    def claim_for_end(self, fingerprint: str) -> ExternoClaim:
        ctx = self._get_context(fingerprint)
        if not ctx:
            return ExternoClaim(result="missing", context={})
        state = str(ctx.get("state") or STATE_PENDING)
        if state == STATE_FINALIZED:
            return ExternoClaim(result="finalized", context=ctx)
        if state == STATE_FINALIZING:
            return ExternoClaim(result="busy", context=ctx)
        lease_token = secrets.token_hex(16)
        ctx["state"] = STATE_FINALIZING
        ctx["lease_token"] = lease_token
        self._put_context(fingerprint, ctx, finalized=False)
        return ExternoClaim(result="claimed", context=ctx, lease_token=lease_token)

    def stored_data_to_sign(self, fingerprint: str) -> Optional[str]:
        ctx = self._get_context(fingerprint)
        if not ctx:
            return None
        value = ctx.get("dataToSign")
        return value if value else None

    def remember_data_to_sign(self, fingerprint: str, data_to_sign: str) -> None:
        ctx = self._get_context(fingerprint)
        if not ctx:
            return
        ctx["dataToSign"] = data_to_sign
        self._put_context(fingerprint, ctx, finalized=False)

    def complete(self, fingerprint: str, lease_token: Optional[str]) -> str:
        ctx = self._get_context(fingerprint)
        if not ctx or str(ctx.get("lease_token") or "") != str(lease_token or ""):
            return "mismatch"
        ctx["state"] = STATE_FINALIZED
        ctx["lease_token"] = None
        self._put_context(fingerprint, ctx, finalized=True)
        return STATE_FINALIZED

    def release_claim(self, fingerprint: str, lease_token: Optional[str]) -> str:
        ctx = self._get_context(fingerprint)
        if not ctx or str(ctx.get("lease_token") or "") != str(lease_token or ""):
            return "mismatch"
        ctx["state"] = STATE_PENDING
        ctx["lease_token"] = None
        self._put_context(fingerprint, ctx, finalized=False)
        return "released"

    def _get_context(self, fingerprint: str) -> Optional[Dict]:
        return self._parse(self.backend.get(self._ctx_key(fingerprint)))

    def _put_context(self, fingerprint: str, ctx: Dict, *, finalized: bool) -> None:
        ttl = self.finalized_ttl_ms if finalized else self.ttl_ms
        self.backend.set(
            self._ctx_key(fingerprint),
            json.dumps(ctx, sort_keys=True, separators=(",", ":")),
            ttl,
        )

    @staticmethod
    def _parse(raw) -> Optional[Dict]:
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return payload if isinstance(payload, dict) else None


def _build_store() -> ExternoContextStore:
    client = _redis_client()
    backend: _StoreBackend = _RedisBackend(client) if client is not None else _MemoryBackend()
    return ExternoContextStore(
        backend,
        key_prefix=getattr(signing_context_store, "key_prefix", "signctx"),
        ttl_ms=getattr(signing_context_store, "ttl_ms", 21600 * 1000),
        lock_ttl_ms=getattr(signing_context_store, "entity_lock_ttl_ms", 120000),
        finalized_ttl_ms=getattr(signing_context_store, "finalized_ttl_ms", 300000),
    )


externo_context_store = _build_store()
