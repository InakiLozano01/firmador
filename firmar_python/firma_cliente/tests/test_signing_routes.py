import base64
import importlib
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


def self_signed_certificate():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "Test Signer"),
            x509.NameAttribute(NameOID.SERIAL_NUMBER, "CUIL 20123456789"),
        ]
    )
    now = datetime.now(timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.DER)


class FakeWorker:
    def __init__(self, certificate_der):
        certificate = x509.load_der_x509_certificate(certificate_der)
        self.certificates = [
            {
                "certificate": base64.b64encode(certificate_der).decode("ascii"),
                "subject": certificate.subject.rfc4514_string(),
            }
        ]
        self.selected_indices = []
        self.sign_calls = []
        self.close_count = 0

    def select_certificate(self, index):
        self.selected_indices.append(index)

    def sign(self, data_to_sign):
        self.sign_calls.append(data_to_sign)
        return ["signed-value"]

    def close(self):
        self.close_count += 1


class SigningRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.main = importlib.import_module("main")
        cls.certificate_der = self_signed_certificate()

    def setUp(self):
        self.assertTrue(
            hasattr(self.main, "transaction_manager"),
            "main routes do not use one-shot signing transactions",
        )
        self.main.transaction_manager.discard_all()

    def _open_transaction(self, worker, origin):
        ui_calls = []

        def run_ui(name, args=()):
            ui_calls.append((name, args))
            return {
                "select_token_slot": 0,
                "get_pin_from_user": "1234",
                "select_certificate": 0,
            }.get(name)

        with (
            patch.object(self.main, "load_token_library_mapping", return_value={"Reader A": "driver.dll"}),
            patch.object(
                self.main,
                "list_tokens_internal",
                return_value=[{"reader": "Reader A", "ATR": [1, 2, 3]}],
            ),
            patch.object(
                self.main,
                "get_token_unique_id_internal",
                return_value=("010203", "Reader A"),
            ),
            patch.object(
                self.main,
                "is_token_library_path_usable",
                return_value=True,
            ),
            patch.object(self.main, "run_ui", side_effect=run_ui),
            patch.object(self.main.PKCS11WorkerClient, "start", return_value=worker),
            patch.object(
                self.main,
                "get_full_chain",
                return_value=([self.certificate_der], 200),
            ),
        ):
            response = self.main.app.test_client().get(
                "/rest/certificates",
                headers={"Origin": origin},
            )
        return response, ui_calls

    def test_one_pin_transaction_signs_one_batch_then_is_consumed(self):
        worker = FakeWorker(self.certificate_der)
        origin = "https://dynamic.example"

        certificate_response, ui_calls = self._open_transaction(worker, origin)

        self.assertEqual(200, certificate_response.status_code)
        certificate_payload = certificate_response.get_json()["response"]
        pin_call = next(call for call in ui_calls if call[0] == "get_pin_from_user")
        self.assertEqual(("python", origin), pin_call[1])
        self.assertEqual([0], worker.selected_indices)

        sign_payload = {
            "tokenId": certificate_payload["tokenId"]["id"],
            "keyId": certificate_payload["keyId"],
            "dataToSign": ["cGF5bG9hZA=="],
        }
        client = self.main.app.test_client()
        first_sign = client.post(
            "/rest/sign",
            json=sign_payload,
            headers={"Origin": origin},
        )
        second_sign = client.post(
            "/rest/sign",
            json=sign_payload,
            headers={"Origin": origin},
        )

        self.assertEqual(200, first_sign.status_code)
        self.assertEqual(["signed-value"], first_sign.get_json()["response"]["signatures"])
        self.assertEqual(404, second_sign.status_code)
        self.assertEqual([["cGF5bG9hZA=="]], worker.sign_calls)
        self.assertEqual(1, worker.close_count)

    def test_different_origin_cannot_consume_transaction(self):
        worker = FakeWorker(self.certificate_der)
        trusted_origin = "https://trusted.example"
        certificate_response, _ = self._open_transaction(worker, trusted_origin)
        certificate_payload = certificate_response.get_json()["response"]
        sign_payload = {
            "tokenId": certificate_payload["tokenId"]["id"],
            "keyId": certificate_payload["keyId"],
            "dataToSign": ["cGF5bG9hZA=="],
        }
        client = self.main.app.test_client()

        rejected = client.post(
            "/rest/sign",
            json=sign_payload,
            headers={"Origin": "https://different.example"},
        )
        accepted = client.post(
            "/rest/sign",
            json=sign_payload,
            headers={"Origin": trusted_origin},
        )

        self.assertEqual(403, rejected.status_code)
        self.assertEqual(200, accepted.status_code)
        self.assertEqual(1, len(worker.sign_calls))

    def test_second_certificate_flow_is_rejected_while_transaction_is_active(self):
        worker = FakeWorker(self.certificate_der)
        token_id = self.main.transaction_manager.create(worker, None, "KEY")
        try:
            with (
                patch.object(
                    self.main,
                    "load_token_library_mapping",
                    return_value={},
                ),
                patch.object(self.main, "list_tokens_internal", return_value=[]),
                patch.object(
                    self.main,
                    "run_ui",
                    side_effect=AssertionError("active transaction must reject before UI"),
                ),
            ):
                response = self.main.app.test_client().get("/rest/certificates")
        finally:
            self.main.transaction_manager.discard(token_id)

        self.assertEqual(409, response.status_code)

    def test_oversized_batch_is_rejected_without_consuming_transaction(self):
        worker = FakeWorker(self.certificate_der)
        origin = "https://dynamic.example"
        certificate_response, _ = self._open_transaction(worker, origin)
        certificate_payload = certificate_response.get_json()["response"]
        client = self.main.app.test_client()
        common = {
            "tokenId": certificate_payload["tokenId"]["id"],
            "keyId": certificate_payload["keyId"],
        }

        with patch.object(self.main, "MAX_SIGNING_ITEMS", 1):
            rejected = client.post(
                "/rest/sign",
                json={**common, "dataToSign": ["YQ==", "Yg=="]},
                headers={"Origin": origin},
            )
        accepted = client.post(
            "/rest/sign",
            json={**common, "dataToSign": ["YQ=="]},
            headers={"Origin": origin},
        )

        self.assertEqual(413, rejected.status_code)
        self.assertEqual(200, accepted.status_code)
        self.assertEqual([["YQ=="]], worker.sign_calls)

    def test_oversized_signing_item_is_rejected_before_token_use(self):
        worker = FakeWorker(self.certificate_der)
        origin = "https://dynamic.example"
        certificate_response, _ = self._open_transaction(worker, origin)
        certificate_payload = certificate_response.get_json()["response"]

        with patch.object(self.main, "MAX_SIGNING_ITEM_CHARS", 4):
            response = self.main.app.test_client().post(
                "/rest/sign",
                json={
                    "tokenId": certificate_payload["tokenId"]["id"],
                    "keyId": certificate_payload["keyId"],
                    "dataToSign": ["12345"],
                },
                headers={"Origin": origin},
            )

        self.assertEqual(413, response.status_code)
        self.assertEqual([], worker.sign_calls)

    def test_stale_driver_mapping_prompts_for_replacement(self):
        worker = FakeWorker(self.certificate_der)
        ui_calls = []

        def run_ui(name, args=()):
            ui_calls.append(name)
            return {
                "select_token_slot": 0,
                "select_library_file": "replacement.dll",
                "get_pin_from_user": "1234",
                "select_certificate": 0,
            }.get(name)

        def usable(path):
            return path == "replacement.dll"

        with (
            patch.object(
                self.main,
                "load_token_library_mapping",
                return_value={"Reader A": "missing.dll"},
            ),
            patch.object(
                self.main,
                "list_tokens_internal",
                return_value=[{"reader": "Reader A", "ATR": [1, 2, 3]}],
            ),
            patch.object(
                self.main,
                "get_token_unique_id_internal",
                return_value=("010203", "Reader A"),
            ),
            patch.object(
                self.main,
                "is_token_library_path_usable",
                side_effect=usable,
            ),
            patch.object(self.main, "save_token_library_mapping") as save_mapping,
            patch.object(self.main, "run_ui", side_effect=run_ui),
            patch.object(self.main.PKCS11WorkerClient, "start", return_value=worker),
            patch.object(
                self.main,
                "get_full_chain",
                return_value=([self.certificate_der], 200),
            ),
        ):
            response = self.main.app.test_client().get(
                "/rest/certificates",
                headers={"Origin": "https://dynamic.example"},
            )

        self.assertEqual(200, response.status_code)
        self.assertIn("select_library_file", ui_calls)
        saved_mapping = save_mapping.call_args.args[0]
        self.assertNotIn("Reader A", saved_mapping)
        self.assertEqual("replacement.dll", saved_mapping["010203"])


if __name__ == "__main__":
    unittest.main()
