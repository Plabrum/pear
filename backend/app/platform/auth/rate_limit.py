from __future__ import annotations

import time
from abc import ABC, abstractmethod

from redis.asyncio import Redis

from app.config import Config

# Defaults: 5 sends per 5-minute window per (subject + IP). Tunable per call.
DEFAULT_LIMIT = 5
DEFAULT_WINDOW_SECONDS = 300

_KEY_PREFIX = "ratelimit:"


class BaseRateLimiter(ABC):
    def __init__(self, limit: int = DEFAULT_LIMIT, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        self.limit = limit
        self.window_seconds = window_seconds

    @abstractmethod
    async def allow(self, key: str) -> bool:
        """Return True if `key` is within budget for the current window, else False."""


class InMemoryRateLimiter(BaseRateLimiter):
    """Process-local fixed-window counters — dev/test only."""

    def __init__(self, limit: int = DEFAULT_LIMIT, window_seconds: int = DEFAULT_WINDOW_SECONDS):
        super().__init__(limit, window_seconds)
        # key -> (count, window_start_epoch)
        self._counters: dict[str, tuple[int, float]] = {}

    async def allow(self, key: str) -> bool:
        now = time.time()
        count, started = self._counters.get(key, (0, now))
        if now - started >= self.window_seconds:
            count, started = 0, now  # window rolled over
        count += 1
        self._counters[key] = (count, started)
        return count <= self.limit


class RedisRateLimiter(BaseRateLimiter):
    """Redis-backed fixed-window counter (INCR + EXPIRE on first hit)."""

    def __init__(
        self,
        redis_url: str,
        limit: int = DEFAULT_LIMIT,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
    ):
        super().__init__(limit, window_seconds)
        self._redis: Redis = Redis.from_url(redis_url, decode_responses=True)

    async def allow(self, key: str) -> bool:
        redis_key = f"{_KEY_PREFIX}{key}"
        count = await self._redis.incr(redis_key)
        if count == 1:
            # First hit in the window — start the TTL clock.
            await self._redis.expire(redis_key, self.window_seconds)
        return count <= self.limit


def build_rate_limiter(config: Config) -> BaseRateLimiter:
    """In-memory limiter in local/dev/testing; Redis-backed otherwise."""
    if config.ENV in {"development", "local", "testing"}:
        return InMemoryRateLimiter()
    return RedisRateLimiter(config.REDIS_URL)
