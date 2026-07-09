from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod

import httpx
import jwt

from app.config import Config

logger = logging.getLogger(__name__)

_ALGORITHM = "ES256"
_TOKEN_URL = "https://appleid.apple.com/auth/token"
_REVOKE_URL = "https://appleid.apple.com/auth/revoke"
# Apple's `client_secret` JWT must expire within 6 months; refresh comfortably
# under that (and cache so we don't re-sign per call).
_JWT_TTL_SECONDS = 60 * 60 * 24 * 30
_REQUEST_TIMEOUT_SECONDS = 10.0


class AppleClientSecretSigner:
    """Signs + caches the Apple outbound `client_secret` JWT (ES256).

    Mirrors `APNsJWTSigner` — one signer instance per process, re-minted only
    once the cached token nears its TTL.
    """

    def __init__(self, *, key: str, key_id: str, team_id: str, client_id: str) -> None:
        self._key = key
        self._key_id = key_id
        self._team_id = team_id
        self._client_id = client_id
        self._token: str | None = None
        self._issued_at: float = 0.0

    def token(self) -> str:
        now = time.time()
        if self._token is not None and (now - self._issued_at) < _JWT_TTL_SECONDS:
            return self._token
        self._token = jwt.encode(
            {
                "iss": self._team_id,
                "iat": int(now),
                "exp": int(now) + _JWT_TTL_SECONDS,
                "aud": "https://appleid.apple.com",
                "sub": self._client_id,
            },
            self._key,
            algorithm=_ALGORITHM,
            headers={"alg": _ALGORITHM, "kid": self._key_id},
        )
        self._issued_at = now
        return self._token


class BaseAppleOAuthClient(ABC):
    @abstractmethod
    async def exchange_code(self, code: str) -> str | None:
        """Exchange an authorization code for a refresh token. Never raises."""

    @abstractmethod
    async def revoke_token(self, refresh_token: str) -> bool:
        """Revoke a previously-issued refresh token. Never raises."""


class LocalAppleOAuthClient(BaseAppleOAuthClient):
    """Dev/test: fabricates a refresh token, logs revokes instead of calling Apple."""

    async def exchange_code(self, code: str) -> str | None:
        logger.info("LOCAL APPLE OAUTH exchange_code (not sent to Apple) code=%s", code)
        return f"local-refresh-token-{code}"

    async def revoke_token(self, refresh_token: str) -> bool:
        logger.info("LOCAL APPLE OAUTH revoke_token (not sent to Apple) token=%s", refresh_token)
        return True


class AppleOAuthClient(BaseAppleOAuthClient):
    """Outbound Apple OAuth: code exchange (`/auth/token`) + grant revoke (`/auth/revoke`)."""

    def __init__(self, config: Config) -> None:
        self._client_id = config.APPLE_CLIENT_ID
        self._signer = AppleClientSecretSigner(
            key=config.APPLE_PRIVATE_KEY,
            key_id=config.APPLE_KEY_ID,
            team_id=config.APPLE_TEAM_ID,
            client_id=config.APPLE_CLIENT_ID,
        )

    async def exchange_code(self, code: str) -> str | None:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._signer.token(),
            "code": code,
            "grant_type": "authorization_code",
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(_TOKEN_URL, data=payload)
        except httpx.HTTPError as e:
            logger.warning("Apple code exchange failed (transport) err=%s", e)
            return None

        if resp.status_code != 200:
            logger.warning("Apple code exchange rejected status=%s body=%s", resp.status_code, resp.text)
            return None

        refresh_token = resp.json().get("refresh_token")
        if not refresh_token:
            logger.warning("Apple code exchange response missing refresh_token")
            return None
        return refresh_token

    async def revoke_token(self, refresh_token: str) -> bool:
        payload = {
            "client_id": self._client_id,
            "client_secret": self._signer.token(),
            "token": refresh_token,
            "token_type_hint": "refresh_token",
        }
        try:
            async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(_REVOKE_URL, data=payload)
        except httpx.HTTPError as e:
            logger.warning("Apple grant revoke failed (transport) err=%s", e)
            return False

        if resp.status_code == 200:
            return True

        logger.warning("Apple grant revoke rejected status=%s body=%s", resp.status_code, resp.text)
        return False


def build_apple_oauth_client(config: Config) -> BaseAppleOAuthClient:
    """Local fabricated client in dev/test (or when Apple OAuth creds are absent); real client in prod."""
    if config.ENV in {"development", "local", "testing"} or not config.APPLE_PRIVATE_KEY:
        return LocalAppleOAuthClient()
    return AppleOAuthClient(config)
