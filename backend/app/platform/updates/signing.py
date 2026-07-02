from __future__ import annotations

import base64

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from app.config import Config


def sign_manifest(body: bytes, config: Config) -> str | None:
    """RSA-SHA256 (PKCS#1 v1.5) signature over the raw manifest JSON, base64-encoded.

    Returns None (unsigned) when no signing key is configured — local/dev/testing
    unless a test injects one. `expo-updates`' `codeSigningCertificate` on the
    client is what actually enforces "reject unsigned manifests" in prod; here we
    only need the private-key half.
    """
    if not config.UPDATES_SIGNING_PRIVATE_KEY:
        return None
    private_key = serialization.load_pem_private_key(
        base64.b64decode(config.UPDATES_SIGNING_PRIVATE_KEY),
        password=None,
    )
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise TypeError(f"UPDATES_SIGNING_PRIVATE_KEY must be an RSA key, got {type(private_key).__name__}")
    signature = private_key.sign(body, padding.PKCS1v15(), hashes.SHA256())
    return base64.b64encode(signature).decode()
