from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

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


def lock_entity_id(id_documento, id_firmante, ancla) -> str:
    return f"{id_documento}:{id_firmante}:{ancla}"


def _redis_client():
    client = getattr(signing_context_store, "client", None)
    if client is None:
        return None
    if not callable(getattr(client, "set", None)) or not callable(getattr(client, "get", None)):
        return None
    return client


class ExternoContextStore:
    def __init__(self, client=None, *, key_prefix="signctx", ttl_ms=21600000, lock_ttl_ms=120000, finalized_ttl_ms=300000):
        self.client = client
        self.key_prefix = key_prefix
        self.ttl_ms = ttl_ms
        self.lock_ttl_ms = lock_ttl_ms
        self.finalized_ttl_ms = finalized_ttl_ms
        self._locks: Dict[str, str] = {}
        self._contexts: Dict[str, Dict] = {}

    def _lock_key(self, entity_id: str) -> str:
        return f"{self.key_prefix}:externo:lock:{entity_id}"

    def _ctx_key(self, fingerprint: str) -> str:
        return f"{self.key_prefix}:externo:ctx:{fingerprint}"

    def acquire_lock(self, entity_id: str) -> Optional[str]:
        token = secrets.token_hex(16)
        if self.client is None:
            if entity_id in self._locks:
                return None
            self._locks[entity_id] = token
            return token
        acquired = self.client.set(self._lock_key(entity_id), token, px=self.lock_ttl_ms, nx=True)
        if not acquired:
            return None
        return token

    def release_lock(self, entity_id: str, token: Optional[str]) -> None:
        if not token or not entity_id:
            return
        if self.client is None:
            if self._locks.get(entity_id) == token:
                self._locks.pop(entity_id, None)
            return
        key = self._lock_key(entity_id)
        current = self.client.get(key)
        if current == token:
            self.client.delete(key)

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
        if self.client is None:
            existing = self._contexts.get(fingerprint)
            if existing:
                return existing, "hit"
            self._contexts[fingerprint] = dict(payload)
            return self._contexts[fingerprint], "created"

        key = self._ctx_key(fingerprint)
        created = self.client.set(
            key,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            px=self.ttl_ms,
            nx=True,
        )
        if created:
            return payload, "created"
        existing = self._parse(self.client.get(key))
        if existing:
            return existing, "hit"
        self.client.set(
            key,
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            px=self.ttl_ms,
            nx=True,
        )
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
        if self.client is None:
            stored = self._contexts.get(fingerprint)
            return dict(stored) if stored else None
        return self._parse(self.client.get(self._ctx_key(fingerprint)))

    def _put_context(self, fingerprint: str, ctx: Dict, *, finalized: bool) -> None:
        ttl = self.finalized_ttl_ms if finalized else self.ttl_ms
        if self.client is None:
            self._contexts[fingerprint] = dict(ctx)
            return
        self.client.set(
            self._ctx_key(fingerprint),
            json.dumps(ctx, sort_keys=True, separators=(",", ":")),
            px=ttl,
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
    return ExternoContextStore(
        client=client,
        key_prefix=getattr(signing_context_store, "key_prefix", "signctx"),
        ttl_ms=getattr(signing_context_store, "ttl_ms", 21600 * 1000),
        lock_ttl_ms=getattr(signing_context_store, "entity_lock_ttl_ms", 120000),
        finalized_ttl_ms=getattr(signing_context_store, "finalized_ttl_ms", 300000),
    )


externo_context_store = _build_store()
