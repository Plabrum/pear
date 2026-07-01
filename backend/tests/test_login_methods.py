from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import TestConfig
from app.platform.auth.clients.apple import AppleAuthError, LocalAppleVerifier

# Magic-link tokens now live in Postgres (HMAC-hashed, single-use via `used_at`); the
# issue/consume/replay/expiry behavior is exercised end-to-end in test_auth_provider.py.
# Rate limiting on /magic-link/request is Litestar's built-in RateLimitConfig
# middleware — its 429 behavior is exercised in test_auth_provider.py.


# ── Apple verifier (injected test key) ────────────────────────────────────────


def _es256_keypair() -> tuple[str, str]:
    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _apple_config() -> tuple[TestConfig, str]:
    priv, pub = _es256_keypair()
    cfg = TestConfig()
    cfg.APPLE_CLIENT_ID = "com.plabrum.wingmate"
    cfg.APPLE_ISSUER = "https://appleid.apple.com"
    cfg.APPLE_TEST_PUBLIC_KEY = pub
    return cfg, priv


def _apple_token(
    private_pem: str, *, aud: str, iss: str, exp_delta: timedelta, sub: str = "apple-sub-1", **extra
) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
        **extra,
    }
    return jwt.encode(claims, private_pem, algorithm="ES256")


async def test_apple_valid_token() -> None:
    cfg, priv = _apple_config()
    token = _apple_token(
        priv,
        aud=cfg.APPLE_CLIENT_ID,
        iss=cfg.APPLE_ISSUER,
        exp_delta=timedelta(minutes=5),
        email="apple@example.com",
        email_verified="true",
    )
    identity = await LocalAppleVerifier(cfg).verify(token)
    assert identity.subject == "apple-sub-1"
    assert identity.email == "apple@example.com"
    assert identity.email_verified is True


async def test_apple_wrong_aud_rejected() -> None:
    cfg, priv = _apple_config()
    token = _apple_token(priv, aud="someone.else", iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=5))
    with pytest.raises(AppleAuthError):
        await LocalAppleVerifier(cfg).verify(token)


async def test_apple_expired_rejected() -> None:
    cfg, priv = _apple_config()
    token = _apple_token(priv, aud=cfg.APPLE_CLIENT_ID, iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=-5))
    with pytest.raises(AppleAuthError):
        await LocalAppleVerifier(cfg).verify(token)


async def test_apple_tampered_signature_rejected() -> None:
    cfg, priv = _apple_config()
    token = _apple_token(priv, aud=cfg.APPLE_CLIENT_ID, iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=5))
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    with pytest.raises(AppleAuthError):
        await LocalAppleVerifier(cfg).verify(tampered)
