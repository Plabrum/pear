"""Magic-link token store (email login).

The magic-link flow mints a short-lived, single-use token bound to a normalized
email and hands it to the user via an email link. Verification consumes the token
exactly once — a replayed token is rejected (the store deletes it on consume), and
an expired token is rejected (TTL eviction). This module owns ONLY the token
lifecycle; the routes (`routes_methods.py`) own delivery + the identity bootstrap.

Two backends, selected by ENV (mirroring `LocalOtpClient` / `LocalEmailClient`):

  * `RedisMagicLinkStore` — production: a Redis key `magiclink:<token>` -> email
    with a TTL of `config.MAGIC_LINK_TTL_SECONDS`. `consume` is atomic
    (GETDEL) so two concurrent verifies cannot both win.
  * `InMemoryMagicLinkStore` — dev/testing: a process-local dict with manual
    expiry checks, so local/e2e auth needs no live Redis.

The token itself is opaque (`secrets.token_urlsafe`) — it carries no claims; all
state (which email, expiry, single-use) lives in the store. That keeps the email
link unguessable and revocable without a verification key.
"""

from __future__ import annotations

import secrets
import time
from abc import ABC, abstractmethod

from redis.asyncio import Redis

from app.config import Config

_KEY_PREFIX = "magiclink:"


class BaseMagicLinkStore(ABC):
    """Mint / consume single-use, TTL-bound magic-link tokens (token -> email)."""

    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def _new_token() -> str:
        return secrets.token_urlsafe(32)

    @abstractmethod
    async def issue(self, email: str) -> str:
        """Mint a token bound to `email`, store it with the configured TTL, return it."""

    @abstractmethod
    async def consume(self, token: str) -> str | None:
        """Atomically consume a token: return its email once, then `None` forever.

        Returns `None` for unknown / already-consumed / expired tokens (replay and
        expiry both fail the same way — the caller maps that to a 401).
        """


class InMemoryMagicLinkStore(BaseMagicLinkStore):
    """Process-local token store for dev / tests — no Redis dependency."""

    def __init__(self, ttl_seconds: int):
        super().__init__(ttl_seconds)
        # token -> (email, expires_at_monotonic_epoch)
        self._tokens: dict[str, tuple[str, float]] = {}

    async def issue(self, email: str) -> str:
        token = self._new_token()
        self._tokens[token] = (email, time.time() + self.ttl_seconds)
        return token

    async def consume(self, token: str) -> str | None:
        entry = self._tokens.pop(token, None)  # single-use: pop regardless
        if entry is None:
            return None
        email, expires_at = entry
        if time.time() >= expires_at:
            return None
        return email


class RedisMagicLinkStore(BaseMagicLinkStore):
    """Redis-backed token store — atomic single-use consume via GETDEL."""

    def __init__(self, ttl_seconds: int, redis_url: str):
        super().__init__(ttl_seconds)
        self._redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    @staticmethod
    def _key(token: str) -> str:
        return f"{_KEY_PREFIX}{token}"

    async def issue(self, email: str) -> str:
        token = self._new_token()
        await self._redis.set(self._key(token), email, ex=self.ttl_seconds)
        return token

    async def consume(self, token: str) -> str | None:
        # GETDEL is atomic: returns the value and deletes the key in one round trip,
        # so a replayed/concurrent verify gets None. Expiry is handled by the TTL.
        value = await self._redis.getdel(self._key(token))
        if value is None:
            return None
        # decode_responses=True yields str, but the stub union still includes bytes.
        return value.decode() if isinstance(value, bytes) else str(value)


def build_magic_link_store(config: Config) -> BaseMagicLinkStore:
    """In-memory store in local/dev/testing; Redis-backed otherwise."""
    if config.ENV in {"development", "local", "testing"}:
        return InMemoryMagicLinkStore(config.MAGIC_LINK_TTL_SECONDS)
    return RedisMagicLinkStore(config.MAGIC_LINK_TTL_SECONDS, config.REDIS_URL)
