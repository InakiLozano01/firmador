"""One-shot authorization state for a single token signing batch."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol
from uuid import uuid4


class SigningWorker(Protocol):
    def sign(self, data_to_sign: list[str]) -> list[str]: ...

    def close(self) -> None: ...


class SigningTransactionError(Exception):
    status_code = 400


class TransactionNotFoundError(SigningTransactionError):
    status_code = 404


class TransactionExpiredError(SigningTransactionError):
    status_code = 410


class TransactionOriginMismatchError(SigningTransactionError):
    status_code = 403


class TransactionKeyMismatchError(SigningTransactionError):
    status_code = 409


class TransactionInProgressError(SigningTransactionError):
    status_code = 409


@dataclass
class _SigningTransaction:
    worker: SigningWorker
    origin: str | None
    key_id: str
    expires_at: float
    timer: Any | None = None


class SigningTransactionManager:
    """Owns short-lived workers and consumes each authorization exactly once."""

    def __init__(
        self,
        ttl_seconds: float = 300,
        clock: Callable[[], float] = time.monotonic,
        timer_factory: Callable[[float, Callable[[], None]], Any] = threading.Timer,
    ) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._timer_factory = timer_factory
        self._transactions: dict[str, _SigningTransaction] = {}
        self._lock = threading.Lock()

    def create(
        self,
        worker: SigningWorker,
        origin: str | None,
        key_id: str,
    ) -> str:
        token_id = str(uuid4())
        transaction = _SigningTransaction(
            worker=worker,
            origin=origin,
            key_id=key_id,
            expires_at=self._clock() + self._ttl_seconds,
        )
        timer = self._timer_factory(
            self._ttl_seconds,
            lambda: self._expire(token_id),
        )
        if hasattr(timer, "daemon"):
            timer.daemon = True
        transaction.timer = timer
        with self._lock:
            if self._transactions:
                raise TransactionInProgressError(
                    "Another signing transaction is already active."
                )
            self._transactions[token_id] = transaction
        timer.start()
        return token_id

    def has_active_transaction(self) -> bool:
        with self._lock:
            return bool(self._transactions)

    def _expire(self, token_id: str) -> None:
        with self._lock:
            transaction = self._transactions.pop(token_id, None)
        if transaction is not None:
            transaction.worker.close()

    def consume(
        self,
        token_id: str,
        key_id: str,
        origin: str | None,
        data_to_sign: list[str],
    ) -> list[str]:
        with self._lock:
            transaction = self._transactions.get(token_id)
            if transaction is None:
                raise TransactionNotFoundError("Signing transaction not found.")
            if self._clock() >= transaction.expires_at:
                self._transactions.pop(token_id, None)
                expired = True
            else:
                expired = False
                if transaction.origin != origin:
                    raise TransactionOriginMismatchError(
                        "Signing transaction belongs to a different origin."
                    )
                if transaction.key_id != key_id:
                    raise TransactionKeyMismatchError(
                        "Selected signing key does not match the transaction."
                    )
                self._transactions.pop(token_id, None)

        if transaction.timer is not None:
            transaction.timer.cancel()
        if expired:
            transaction.worker.close()
            raise TransactionExpiredError("Signing transaction expired.")

        try:
            return transaction.worker.sign(data_to_sign)
        finally:
            transaction.worker.close()

    def discard(self, token_id: str) -> bool:
        with self._lock:
            transaction = self._transactions.pop(token_id, None)
        if transaction is None:
            return False
        if transaction.timer is not None:
            transaction.timer.cancel()
        transaction.worker.close()
        return True

    def discard_all(self) -> None:
        with self._lock:
            transactions = list(self._transactions.values())
            self._transactions.clear()
        for transaction in transactions:
            if transaction.timer is not None:
                transaction.timer.cancel()
            transaction.worker.close()
