"""Isolated PKCS#11 runtime and JSON-line worker process."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
from base64 import b64encode
from pathlib import Path
from typing import Any

import PyKCS11
from cryptography import x509

from signing import sign_multiple_data_internal


class PKCS11WorkerError(Exception):
    def __init__(self, message: str, error_type: str | None = None):
        super().__init__(message)
        self.error_type = error_type


class SlotResolutionError(PKCS11WorkerError):
    pass


class PrivateKeyBindingError(PKCS11WorkerError):
    pass


class WorkerTimeoutError(PKCS11WorkerError):
    pass


def _normalized_slot_name(value: Any) -> str:
    return " ".join(str(value).replace("\x00", " ").lower().split())


def resolve_pkcs11_slot(
    library: PyKCS11.PyKCS11Lib,
    slots: list[Any],
    selected_reader_name: str,
) -> Any:
    """Resolve the PC/SC reader selected by the user to one PKCS#11 slot."""
    if not slots:
        raise SlotResolutionError("No PKCS#11 token-present slots were found.")
    if len(slots) == 1:
        return slots[0]

    selected = _normalized_slot_name(selected_reader_name)
    matches = []
    descriptions = []
    for slot in slots:
        description = _normalized_slot_name(library.getSlotInfo(slot).slotDescription)
        descriptions.append(description)
        if selected == description or selected in description or description in selected:
            matches.append(slot)

    if len(matches) == 1:
        return matches[0]
    raise SlotResolutionError(
        "The selected smartcard reader could not be mapped unambiguously "
        f"to a PKCS#11 slot. Available slots: {descriptions}"
    )


def find_private_key_for_certificate(
    session: PyKCS11.Session,
    certificate_id: bytes,
) -> Any:
    """Bind the selected certificate to exactly one private key."""
    template = [(PyKCS11.CKA_CLASS, PyKCS11.CKO_PRIVATE_KEY)]
    if certificate_id:
        template.append((PyKCS11.CKA_ID, certificate_id))
    keys = session.findObjects(template)
    if len(keys) != 1:
        raise PrivateKeyBindingError(
            "The selected certificate does not map to exactly one private key."
        )
    return keys[0]


class PKCS11Runtime:
    """Owns one loaded library and one logged-in session inside the worker."""

    def __init__(self) -> None:
        self._library: PyKCS11.PyKCS11Lib | None = None
        self._session: PyKCS11.Session | None = None
        self._certificates: list[dict[str, Any]] = []
        self._selected_key: Any | None = None

    def open(
        self,
        library_path: str,
        pin: str,
        selected_reader_name: str,
    ) -> list[dict[str, str]]:
        self.close()
        library = PyKCS11.PyKCS11Lib()
        session = None
        try:
            library.load(library_path)
            slots = library.getSlotList(tokenPresent=True)
            slot = resolve_pkcs11_slot(library, slots, selected_reader_name)
            session = library.openSession(slot, PyKCS11.CKF_SERIAL_SESSION)
            session.login(pin)

            records: list[dict[str, Any]] = []
            template = [(PyKCS11.CKA_CLASS, PyKCS11.CKO_CERTIFICATE)]
            attributes = [
                PyKCS11.CKA_VALUE,
                PyKCS11.CKA_SUBJECT,
                PyKCS11.CKA_ID,
            ]
            for handle in session.findObjects(template):
                values = session.getAttributeValue(handle, attributes)
                cert_der = bytes(values[0])
                certificate = x509.load_der_x509_certificate(cert_der)
                cert_id = bytes(values[2] or b"")
                records.append(
                    {
                        "handle": handle,
                        "certificate_id": cert_id,
                        "certificate_der": cert_der,
                        "subject": certificate.subject.rfc4514_string(),
                    }
                )
            if not records:
                raise PKCS11WorkerError(
                    "No certificates were found on the selected token."
                )

            self._library = library
            self._session = session
            self._certificates = records
            return [
                {
                    "certificate": b64encode(record["certificate_der"]).decode("ascii"),
                    "subject": record["subject"],
                }
                for record in records
            ]
        except PyKCS11.PyKCS11Error as exc:
            error_type = None
            if getattr(exc, "rc", None) == PyKCS11.CKR_PIN_INCORRECT:
                error_type = "BAD_PIN"
            elif getattr(exc, "rc", None) == PyKCS11.CKR_PIN_LOCKED:
                error_type = "PIN_LOCKED"
            if session is not None:
                self._close_session(session)
            raise PKCS11WorkerError(str(exc), error_type=error_type) from exc
        except Exception:
            if session is not None:
                self._close_session(session)
            raise

    def select_certificate(self, index: int) -> None:
        if self._session is None:
            raise PKCS11WorkerError("PKCS#11 session is not open.")
        try:
            record = self._certificates[index]
        except IndexError as exc:
            raise PKCS11WorkerError("Invalid certificate selection.") from exc
        self._selected_key = find_private_key_for_certificate(
            self._session,
            record["certificate_id"],
        )

    def sign(self, data_to_sign: list[str]) -> list[str]:
        if self._session is None or self._selected_key is None:
            raise PKCS11WorkerError(
                "A certificate and its private key must be selected before signing."
            )
        return sign_multiple_data_internal(
            self._session,
            data_to_sign,
            private_key_handle=self._selected_key,
        )

    @staticmethod
    def _close_session(session: PyKCS11.Session) -> None:
        try:
            session.logout()
        except Exception:
            pass
        try:
            session.closeSession()
        except Exception:
            pass

    def close(self) -> None:
        if self._session is not None:
            self._close_session(self._session)
        self._session = None
        self._library = None
        self._certificates = []
        self._selected_key = None


def _worker_response(result: Any = None, error: Exception | None = None) -> str:
    if error is None:
        payload = {"ok": True, "result": result}
    else:
        payload = {
            "ok": False,
            "error": str(error),
            "error_type": getattr(error, "error_type", None),
        }
    return json.dumps(payload, ensure_ascii=False)


def serve_worker() -> None:
    runtime = PKCS11Runtime()
    try:
        for line in sys.stdin:
            command = None
            try:
                request = json.loads(line)
                command = request.get("command")
                if command == "open":
                    result = runtime.open(
                        request["library_path"],
                        request["pin"],
                        request["reader_name"],
                    )
                elif command == "select_certificate":
                    runtime.select_certificate(int(request["index"]))
                    result = None
                elif command == "sign":
                    result = runtime.sign(request["data_to_sign"])
                elif command == "close":
                    runtime.close()
                    result = None
                else:
                    raise PKCS11WorkerError(f"Unknown worker command: {command}")
                response = _worker_response(result=result)
            except Exception as exc:
                response = _worker_response(error=exc)
            sys.stdout.write(response + "\n")
            sys.stdout.flush()
            if command == "close":
                break
    finally:
        runtime.close()


class PKCS11WorkerClient:
    """Parent-side Adapter for one persistent PKCS#11 worker process."""

    def __init__(
        self,
        process: subprocess.Popen[str],
        command_timeout: float = 30,
    ) -> None:
        self._process = process
        self._command_timeout = command_timeout
        self._lock = threading.Lock()
        self._closed = False
        self.certificates: list[dict[str, str]] = []

    @classmethod
    def start(
        cls,
        library_path: str,
        pin: str,
        reader_name: str,
        command_timeout: float = 30,
    ) -> "PKCS11WorkerClient":
        if getattr(sys, "frozen", False):
            command = [sys.executable, "--pkcs11-worker"]
        else:
            command = [sys.executable, str(Path(__file__).resolve()), "--serve"]
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        client = cls(process, command_timeout=command_timeout)
        try:
            client.certificates = client._request(
                {
                    "command": "open",
                    "library_path": library_path,
                    "pin": pin,
                    "reader_name": reader_name,
                }
            )
            return client
        except Exception:
            client.close()
            raise

    def _readline_with_timeout(self) -> str:
        if self._process.stdout is None:
            raise PKCS11WorkerError("Worker stdout is unavailable.")
        responses: queue.Queue[str] = queue.Queue(maxsize=1)

        def read_response() -> None:
            responses.put(self._process.stdout.readline())

        threading.Thread(target=read_response, daemon=True).start()
        try:
            return responses.get(timeout=self._command_timeout)
        except queue.Empty as exc:
            self._terminate()
            raise WorkerTimeoutError(
                f"PKCS#11 worker exceeded {self._command_timeout:g} seconds."
            ) from exc

    def _request(self, payload: dict[str, Any]) -> Any:
        with self._lock:
            if self._closed or self._process.poll() is not None:
                raise PKCS11WorkerError("PKCS#11 worker is not running.")
            if self._process.stdin is None:
                raise PKCS11WorkerError("Worker stdin is unavailable.")
            self._process.stdin.write(json.dumps(payload, ensure_ascii=False) + "\n")
            self._process.stdin.flush()
            line = self._readline_with_timeout()
            if not line:
                raise PKCS11WorkerError("PKCS#11 worker exited without a response.")
            response = json.loads(line)
            if not response.get("ok"):
                raise PKCS11WorkerError(
                    response.get("error", "Unknown PKCS#11 worker error."),
                    error_type=response.get("error_type"),
                )
            return response.get("result")

    def select_certificate(self, index: int) -> None:
        self._request({"command": "select_certificate", "index": index})

    def sign(self, data_to_sign: list[str]) -> list[str]:
        return self._request({"command": "sign", "data_to_sign": data_to_sign})

    def _terminate(self) -> None:
        if self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()

    def close(self) -> None:
        if self._closed:
            return
        try:
            if self._process.poll() is None:
                self._request({"command": "close"})
        except Exception:
            pass
        finally:
            self._closed = True
            self._terminate()


if __name__ == "__main__" and "--serve" in sys.argv:
    serve_worker()
