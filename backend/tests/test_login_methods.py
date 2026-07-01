from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.config import TestConfig
from app.platform.auth.clients.apple import AppleAuthError, LocalAppleVerifier
from app.platform.auth.clients.otp import LocalOtpClient
from app.platform.auth.magic_link import InMemoryMagicLinkStore
from app.platform.auth.rate_limit import InMemoryRateLimiter

# ── OTP (local fake) ──────────────────────────────────────────────────────────


async def test_local_otp_accepts_dev_code() -> None:
    client = LocalOtpClient(dev_code="000000")
    await client.send("+15551234567")  # no-op, logs only
    assert await client.check("+15551234567", "000000") is True
    assert await client.check("+15551234567", "999999") is False


# ── Magic-link store ──────────────────────────────────────────────────────────


async def test_magic_link_single_use_and_replay_rejected() -> None:
    store = InMemoryMagicLinkStore(ttl_seconds=900)
    token = await store.issue("dater@example.com")

    # First consume returns the bound email; a replay returns None (single-use).
    assert await store.consume(token) == "dater@example.com"
    assert await store.consume(token) is None


async def test_magic_link_unknown_token_rejected() -> None:
    store = InMemoryMagicLinkStore(ttl_seconds=900)
    assert await store.consume("never-issued") is None


async def test_magic_link_expired_token_rejected() -> None:
    store = InMemoryMagicLinkStore(ttl_seconds=900)
    token = await store.issue("dater@example.com")
    # Force the entry's expiry into the past.
    email, _ = store._tokens[token]  # type: ignore[attr-defined]
    store._tokens[token] = (email, time.time() - 1)  # type: ignore[attr-defined]
    assert await store.consume(token) is None


# ── Rate limiter ──────────────────────────────────────────────────────────────


async def test_rate_limiter_allows_within_budget_then_denies() -> None:
    limiter = InMemoryRateLimiter(limit=3, window_seconds=300)
    key = "otp:+15551234567:1.2.3.4"
    assert [await limiter.allow(key) for _ in range(3)] == [True, True, True]
    assert await limiter.allow(key) is False  # 4th over the budget


async def test_rate_limiter_window_resets() -> None:
    limiter = InMemoryRateLimiter(limit=1, window_seconds=300)
    key = "magic:dater@example.com:1.2.3.4"
    assert await limiter.allow(key) is True
    assert await limiter.allow(key) is False
    # Roll the window start into the past so it resets.
    count, _ = limiter._counters[key]  # type: ignore[attr-defined]
    limiter._counters[key] = (count, time.time() - 301)  # type: ignore[attr-defined]
    assert await limiter.allow(key) is True


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
