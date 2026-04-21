"""Load intermediate/issuer CA certificates from disk and resolve parent for a child cert."""

from __future__ import annotations

import logging
import os
import re
import threading
from typing import List

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import ExtensionOID

from app.config.settings import settings

logger = logging.getLogger(__name__)

_PEM_CERT_BLOCK = re.compile(
    rb"-----BEGIN CERTIFICATE-----\s*.+?\s*-----END CERTIFICATE-----",
    re.DOTALL,
)

_pool_lock = threading.Lock()
_issuer_pool: List[x509.Certificate] | None = None


def _certs_from_pem_blob(data: bytes) -> List[x509.Certificate]:
    certs: List[x509.Certificate] = []
    for block in _PEM_CERT_BLOCK.findall(data):
        try:
            certs.append(x509.load_pem_x509_certificate(block))
        except ValueError:
            continue
    return certs


def _authority_key_extensions_consistent(
    lower: x509.Certificate, candidate_parent: x509.Certificate
) -> bool:
    try:
        aki_ext = lower.extensions.get_extension_for_oid(ExtensionOID.AUTHORITY_KEY_IDENTIFIER)
    except x509.ExtensionNotFound:
        return True

    aki = aki_ext.value

    if aki.key_identifier is not None:
        try:
            ski_ext = candidate_parent.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_KEY_IDENTIFIER
            )
        except x509.ExtensionNotFound:
            pass
        else:
            if ski_ext.value.digest != aki.key_identifier:
                return False

    if aki.authority_cert_serial_number is not None:
        if candidate_parent.serial_number != aki.authority_cert_serial_number:
            return False

    return True


def _issuer_dn_matches_parent_candidate(
    lower_cert: x509.Certificate, candidate_parent: x509.Certificate
) -> bool:
    return candidate_parent.subject == lower_cert.issuer and _authority_key_extensions_consistent(
        lower_cert, candidate_parent
    )


def _load_issuer_pool() -> List[x509.Certificate]:
    global _issuer_pool
    with _pool_lock:
        if _issuer_pool is not None:
            return _issuer_pool
        pool: List[x509.Certificate] = []
        base = settings.ISSUER_POOL_DIR
        if not os.path.isdir(base):
            logger.info("Issuer pool directory missing or not a directory: %s", base)
            _issuer_pool = pool
            return pool
        for name in sorted(os.listdir(base)):
            path = os.path.join(base, name)
            if not os.path.isfile(path) or name.startswith("."):
                continue
            low = name.lower()
            if not (
                low.endswith(".pem")
                or low.endswith(".crt")
                or low.endswith(".cer")
                or low.endswith(".der")
            ):
                continue
            try:
                with open(path, "rb") as f:
                    data = f.read()
            except OSError as e:
                logger.warning("Could not read issuer pool file %s: %s", path, e)
                continue
            if not data:
                continue
            try:
                if b"-----BEGIN" in data:
                    pool.extend(_certs_from_pem_blob(data))
                elif low.endswith(".pem"):
                    pool.extend(_certs_from_pem_blob(data))
                else:
                    try:
                        pool.append(x509.load_der_x509_certificate(data))
                    except ValueError:
                        pool.extend(_certs_from_pem_blob(data))
            except Exception as e_parse:
                logger.warning("Could not parse issuer pool file %s: %s", path, e_parse)
        _issuer_pool = pool
        if pool:
            logger.info("Loaded %s issuer certificate(s) from %s", len(pool), base)
        return pool


def find_matching_issuer(lower_cert: x509.Certificate) -> x509.Certificate | None:
    for candidate in _load_issuer_pool():
        if _issuer_dn_matches_parent_candidate(lower_cert, candidate):
            return candidate
    return None


def resolve_issuer_for_child(child_der: bytes) -> bytes | None:
    """Return issuer certificate DER for the given child certificate DER, or None."""
    try:
        lower = x509.load_der_x509_certificate(child_der)
    except ValueError:
        return None
    issuer = find_matching_issuer(lower)
    if issuer is None:
        return None
    return issuer.public_bytes(serialization.Encoding.DER)
