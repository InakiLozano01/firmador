import base64
import importlib
import io
import json
import sys
import types
import unittest
from pathlib import Path

import PyKCS11


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


def load_worker_module():
    try:
        return importlib.import_module("pkcs11_worker")
    except ModuleNotFoundError as exc:
        raise AssertionError("pkcs11_worker Module has not been implemented") from exc


class FakeLibrary:
    def __init__(self, descriptions):
        self.descriptions = descriptions

    def getSlotInfo(self, slot):
        return types.SimpleNamespace(slotDescription=self.descriptions[slot])


class FakeSession:
    def __init__(self, keys_by_id):
        self.keys_by_id = keys_by_id
        self.templates = []

    def findObjects(self, template):
        self.templates.append(template)
        key_id = next(
            (value for attribute, value in template if attribute == PyKCS11.CKA_ID),
            None,
        )
        return list(self.keys_by_id.get(bytes(key_id or b""), []))


class SlotResolutionTests(unittest.TestCase):
    def test_resolves_selected_reader_to_matching_pkcs11_slot(self):
        module = load_worker_module()
        library = FakeLibrary(
            {
                10: "Unrelated virtual slot",
                20: "Longmai mToken CryptoIDE 0",
            }
        )

        slot = module.resolve_pkcs11_slot(
            library,
            [10, 20],
            "Longmai mToken CryptoIDE 0",
        )

        self.assertEqual(20, slot)

    def test_uses_only_present_slot_when_driver_exposes_one(self):
        module = load_worker_module()
        library = FakeLibrary({37: "Vendor-specific description"})

        self.assertEqual(
            37,
            module.resolve_pkcs11_slot(library, [37], "PC/SC reader name"),
        )

    def test_rejects_ambiguous_slots_instead_of_silently_using_first(self):
        module = load_worker_module()
        library = FakeLibrary({1: "Slot A", 2: "Slot B"})

        with self.assertRaises(module.SlotResolutionError):
            module.resolve_pkcs11_slot(library, [1, 2], "Unknown reader")


class KeyBindingTests(unittest.TestCase):
    def test_binds_private_key_by_certificate_cka_id(self):
        module = load_worker_module()
        selected_key = object()
        session = FakeSession({b"cert-id": [selected_key]})

        result = module.find_private_key_for_certificate(session, b"cert-id")

        self.assertIs(selected_key, result)
        self.assertIn(
            (PyKCS11.CKA_ID, b"cert-id"),
            session.templates[0],
        )

    def test_rejects_missing_key_for_selected_certificate(self):
        module = load_worker_module()
        session = FakeSession({})

        with self.assertRaises(module.PrivateKeyBindingError):
            module.find_private_key_for_certificate(session, b"missing")


class ExplicitSigningKeyTests(unittest.TestCase):
    def test_batch_sign_requires_explicit_selected_key(self):
        signing = importlib.import_module("signing")

        class Session:
            def findObjects(self, _template):
                return [object()]

        with self.assertRaises(TypeError):
            signing.sign_multiple_data_internal(Session(), [])

    def test_batch_sign_uses_explicit_selected_key(self):
        signing = importlib.import_module("signing")

        class Session:
            def findObjects(self, _template):
                raise AssertionError("must not search for the first private key")

            def sign(self, key_handle, data, _mechanism):
                self.key_handle = key_handle
                self.data = data
                return b"signed"

        session = Session()
        try:
            signatures = signing.sign_multiple_data_internal(
                session,
                [base64.b64encode(b"payload").decode("ascii")],
                private_key_handle="selected-key",
            )
        except TypeError as exc:
            raise AssertionError(
                "batch signing does not accept an explicit selected key"
            ) from exc

        self.assertEqual(["c2lnbmVk"], signatures)
        self.assertEqual("selected-key", session.key_handle)
        self.assertEqual(b"payload", session.data)

    def test_rejects_non_base64_signing_payload(self):
        signing = importlib.import_module("signing")

        class Session:
            def sign(self, *_args):
                raise AssertionError("invalid payload must not reach the token")

        with self.assertRaises(signing.InvalidBase64DataError):
            signing.sign_data_with_private_key(Session(), "selected-key", "%%%%")


class WorkerProtocolTests(unittest.TestCase):
    def test_malformed_command_returns_error_and_worker_can_close(self):
        module = load_worker_module()
        stdin = io.StringIO('not-json\n{"command": "close"}\n')
        stdout = io.StringIO()

        original_stdin = module.sys.stdin
        original_stdout = module.sys.stdout
        try:
            module.sys.stdin = stdin
            module.sys.stdout = stdout
            module.serve_worker()
        finally:
            module.sys.stdin = original_stdin
            module.sys.stdout = original_stdout

        responses = [json.loads(line) for line in stdout.getvalue().splitlines()]
        self.assertFalse(responses[0]["ok"])
        self.assertTrue(responses[1]["ok"])


if __name__ == "__main__":
    unittest.main()
