from __future__ import annotations

import base64
import os
import threading
from dataclasses import dataclass
from typing import Dict, List, Tuple, Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from dotenv import load_dotenv

load_dotenv()


class CertificateError(Exception):
    """Custom exception for certificate-related errors"""


class SignatureError(Exception):
    """Custom exception for signature-related errors"""


@dataclass(frozen=True)
class _CachedLocalMaterial:
    key_mtime: float
    cert_mtime: float
    private_key: rsa.RSAPrivateKey
    certificate_payload: Dict[str, Union[str, List[str]]]


_CACHE_LOCK = threading.RLock()
_LOCAL_MATERIAL_CACHE: _CachedLocalMaterial | None = None


def _load_environment_variables() -> Tuple[str, str, str]:
    private_key_password = os.getenv('PRIVATE_KEY_PASSWORD')
    private_key_path = os.getenv('PRIVATE_KEY_PATH')
    certificate_path = os.getenv('CERTIFICATE_PATH')

    if not all([private_key_password, private_key_path, certificate_path]):
        raise CertificateError("Missing required environment variables")

    return private_key_password, private_key_path, certificate_path


def _load_private_key(key_path: str, password: str) -> rsa.RSAPrivateKey:
    try:
        with open(key_path, "rb") as key_file:
            return load_pem_private_key(
                key_file.read(),
                password=password.encode(),
                backend=default_backend()
            )
    except Exception as e:
        raise SignatureError(f"Failed to load private key: {str(e)}") from e


def _load_certificate(cert_path: str) -> bytes:
    try:
        with open(cert_path, "rb") as cert_file:
            return cert_file.read()
    except Exception as e:
        raise CertificateError(f"Failed to read certificate file: {str(e)}") from e


def _load_or_refresh_material() -> _CachedLocalMaterial:
    global _LOCAL_MATERIAL_CACHE

    private_key_password, private_key_path, certificate_path = _load_environment_variables()
    key_mtime = os.path.getmtime(private_key_path)
    cert_mtime = os.path.getmtime(certificate_path)

    with _CACHE_LOCK:
        cache = _LOCAL_MATERIAL_CACHE
        if cache and cache.key_mtime == key_mtime and cache.cert_mtime == cert_mtime:
            return cache

        private_key = _load_private_key(private_key_path, private_key_password)
        certificate_data = _load_certificate(certificate_path)
        cert_base64 = base64.b64encode(certificate_data).decode("utf-8")
        cache = _CachedLocalMaterial(
            key_mtime=key_mtime,
            cert_mtime=cert_mtime,
            private_key=private_key,
            certificate_payload={
                "certificate": cert_base64,
                "certificateChain": [cert_base64],
            },
        )
        _LOCAL_MATERIAL_CACHE = cache
        return cache


def get_signature_value_own(data_to_sign: str) -> str:
    try:
        private_key = _load_or_refresh_material().private_key
        data_to_sign_bytes = base64.b64decode(data_to_sign)
        signature = private_key.sign(
            data_to_sign_bytes,
            padding.PKCS1v15(),
            hashes.SHA256()
        )
        return base64.b64encode(signature).decode("utf-8")
    except Exception as e:
        raise SignatureError(f"Failed to sign data: {str(e)}") from e


def get_certificate_from_local() -> Dict[str, Union[str, List[str]]]:
    try:
        return dict(_load_or_refresh_material().certificate_payload)
    except Exception as e:
        raise CertificateError(f"Failed to process certificate: {str(e)}") from e
