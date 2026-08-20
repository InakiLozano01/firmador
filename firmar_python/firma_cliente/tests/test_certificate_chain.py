import importlib
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import AuthorityInformationAccessOID, NameOID
from flask import Flask


CLIENT_DIR = Path(__file__).resolve().parents[1]
if str(CLIENT_DIR) not in sys.path:
    sys.path.insert(0, str(CLIENT_DIR))


def build_ca(subject, key):
    now = datetime.now(timezone.utc)
    return (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )


def build_child(parent, parent_key, with_aia=False):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    now = datetime.now(timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Child")]))
        .issuer_name(parent.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
    )
    if with_aia:
        builder = builder.add_extension(
            x509.AuthorityInformationAccess(
                [
                    x509.AccessDescription(
                        AuthorityInformationAccessOID.CA_ISSUERS,
                        x509.UniformResourceIdentifier("http://issuer.invalid/ca.der"),
                    )
                ]
            ),
            critical=False,
        )
    return builder.sign(parent_key, hashes.SHA256())


class CertificateChainTrustTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.certificates = importlib.import_module("certificates")
        cls.ca_subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, "Same Subject CA")]
        )
        cls.trusted_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.forged_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.trusted_parent = build_ca(cls.ca_subject, cls.trusted_key)
        cls.forged_parent = build_ca(cls.ca_subject, cls.forged_key)

    def test_parent_candidate_must_verify_child_signature(self):
        child = build_child(self.trusted_parent, self.trusted_key)

        self.assertTrue(
            self.certificates._issuer_dn_matches_parent_candidate(
                child,
                self.trusted_parent,
            )
        )
        self.assertFalse(
            self.certificates._issuer_dn_matches_parent_candidate(
                child,
                self.forged_parent,
            )
        )

    def test_cached_verified_issuer_is_used_before_network(self):
        child = build_child(self.trusted_parent, self.trusted_key, with_aia=True)

        with (
            patch.object(
                self.certificates,
                "_load_issuer_from_cache",
                return_value=self.trusted_parent,
            ),
            patch.object(
                self.certificates,
                "get",
                side_effect=AssertionError("network must not run on a cache hit"),
            ),
        ):
            resolved = self.certificates.get_issuer_cert(child, token_key="token")

        self.assertEqual(self.trusted_parent, resolved)

    def test_chain_deadline_stops_network_before_request_can_hang(self):
        child = build_child(self.trusted_parent, self.trusted_key, with_aia=True)
        child_der = child.public_bytes(serialization.Encoding.DER)

        with (
            patch.object(
                self.certificates,
                "_load_issuer_from_cache",
                return_value=None,
            ),
            patch.object(
                self.certificates,
                "get",
                side_effect=AssertionError("expired chain must not start network"),
            ),
            Flask(__name__).app_context(),
        ):
            _response, status_code = self.certificates.get_full_chain(
                child,
                child_der,
                token_key="deadline-test",
                max_duration_seconds=0,
            )

        self.assertEqual(504, status_code)

    def test_frozen_issuer_cache_uses_per_user_data_directory(self):
        with tempfile.TemporaryDirectory() as local_app_data:
            with (
                patch.object(sys, "frozen", True, create=True),
                patch.dict(os.environ, {"LOCALAPPDATA": local_app_data}),
            ):
                base_dir = self.certificates._client_base_dir()

        self.assertEqual(
            os.path.join(local_app_data, "Tuquito"),
            base_dir,
        )


if __name__ == "__main__":
    unittest.main()
