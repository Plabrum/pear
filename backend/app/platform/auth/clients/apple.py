"""Apple Sign-In identity-token verification.

`POST /auth/apple` sends Apple's `identityToken`; we verify it server-side:
fetch Apple's JWKS (cached), verify the RS256 signature, validate
`iss == https://appleid.apple.com`, `aud == config.APPLE_CLIENT_ID`, and `exp`,
then return the stable `sub` (+ email/email_verified when present — Apple delivers
email only on first authorization).

**Test/dev injection:** when `config.APPLE_TEST_PUBLIC_KEY` is set (PEM), a
locally-signed token is verified against that key instead of Apple's JWKS, so the
suite can mint Apple tokens with a known keypair and exercise valid / wrong-aud /
expired / tampered cases without network access. `config.APPLE_ISSUER` is likewise
overridable in tests.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
import jwt
from jwt import PyJWKClient

from app.config import Config

logger = logging.getLogger(__name__)


class AppleAuthError(Exception):
    """Raised when an Apple identity token fails verification (caller -> 401)."""


@dataclass
class AppleIdentity:
    """Verified Apple identity claims."""

    subject: str
    email: str | None = None
    email_verified: bool = False


class BaseAppleVerifier:
    def __init__(self, config: Config):
        self.config = config

    def _decode(self, token: str, key: object) -> dict:
        try:
            return jwt.decode(
                token,
                key,  # type: ignore[arg-type]
                algorithms=["RS256", "ES256"],
                audience=self.config.APPLE_CLIENT_ID,
                issuer=self.config.APPLE_ISSUER,
            )
        except jwt.PyJWTError as e:
            raise AppleAuthError(f"Invalid Apple identity token: {e}") from e

    @staticmethod
    def _identity_from_claims(claims: dict) -> AppleIdentity:
        sub = claims.get("sub")
        if not sub:
            raise AppleAuthError("Apple token missing `sub`")
        email_verified = claims.get("email_verified")
        if isinstance(email_verified, str):
            email_verified = email_verified.lower() == "true"
        return AppleIdentity(
            subject=str(sub),
            email=claims.get("email"),
            email_verified=bool(email_verified),
        )

    async def verify(self, identity_token: str) -> AppleIdentity:
        raise NotImplementedError


class LocalAppleVerifier(BaseAppleVerifier):
    """Verifies tokens against an injected test public key (no network)."""

    async def verify(self, identity_token: str) -> AppleIdentity:
        claims = self._decode(identity_token, self.config.APPLE_TEST_PUBLIC_KEY)
        return self._identity_from_claims(claims)


class AppleJWKSVerifier(BaseAppleVerifier):
    """Verifies tokens against Apple's published JWKS (cached by PyJWKClient)."""

    def __init__(self, config: Config):
        super().__init__(config)
        # PyJWKClient caches keys in-process and refreshes on key-id miss.
        self._jwk_client = PyJWKClient(config.APPLE_JWKS_URL)

    async def verify(self, identity_token: str) -> AppleIdentity:
        try:
            signing_key = self._jwk_client.get_signing_key_from_jwt(identity_token)
        except (jwt.PyJWTError, httpx.HTTPError) as e:
            raise AppleAuthError(f"Could not resolve Apple signing key: {e}") from e
        claims = self._decode(identity_token, signing_key.key)
        return self._identity_from_claims(claims)


def build_apple_verifier(config: Config) -> BaseAppleVerifier:
    """Local injected-key verifier when a test key is configured; else real JWKS."""
    if config.APPLE_TEST_PUBLIC_KEY:
        return LocalAppleVerifier(config)
    return AppleJWKSVerifier(config)
