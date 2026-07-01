from __future__ import annotations

import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx
import jwt

from app.config import Config

logger = logging.getLogger(__name__)

_ALGORITHM = "ES256"
# APNs rejects provider tokens older than 60 minutes. Refresh comfortably under
# that (Apple also rejects tokens minted *too* frequently, so we cache and reuse).
_JWT_TTL_SECONDS = 50 * 60
# Per-send network budget — APNs is fast; keep the request from stalling an action.
_REQUEST_TIMEOUT_SECONDS = 10.0


@dataclass
class PushSendResult:
    """Outcome of a single APNs delivery.

    ``unregistered`` is True on a 410 (the device token is no longer valid — the
    app was uninstalled), signalling the caller to null the stored token.
    """

    delivered: bool
    unregistered: bool = False


class APNsJWTSigner:
    """Signs + caches the APNs provider JWT (ES256).

    The signed token is reused until it nears expiry, then re-minted once. This is
    the "cache it < 1hr, don't re-sign per send" requirement: a single signer
    instance lives for the process and hands out the same token to every send
    until the TTL lapses.
    """

    def __init__(self, *, key: str, key_id: str, team_id: str) -> None:
        self._key = key
        self._key_id = key_id
        self._team_id = team_id
        self._token: str | None = None
        self._issued_at: float = 0.0

    def token(self) -> str:
        """Return a valid provider JWT, signing a fresh one only when needed."""
        now = time.time()
        if self._token is not None and (now - self._issued_at) < _JWT_TTL_SECONDS:
            return self._token
        self._token = jwt.encode(
            {"iss": self._team_id, "iat": int(now)},
            self._key,
            algorithm=_ALGORITHM,
            headers={"alg": _ALGORITHM, "kid": self._key_id},
        )
        self._issued_at = now
        return self._token


class BasePushClient(ABC):
    @abstractmethod
    async def send(self, token: str, title: str, body: str) -> PushSendResult:
        """Deliver a single alert push. Never raises — returns a result."""


class LocalPushClient(BasePushClient):
    """Logs the push instead of delivering — used for dev and tests."""

    async def send(self, token: str, title: str, body: str) -> PushSendResult:
        logger.info("LOCAL PUSH (not delivered) -> token=%s title=%r body=%r", token, title, body)
        return PushSendResult(delivered=True)


class APNsPushClient(BasePushClient):
    """Direct APNs client: cached ES256 JWT + HTTP/2 POST per device token."""

    def __init__(self, config: Config) -> None:
        self._host = config.APNS_HOST
        self._topic = config.APNS_TOPIC
        self._signer = APNsJWTSigner(
            key=config.APNS_KEY,
            key_id=config.APNS_KEY_ID,
            team_id=config.APNS_TEAM_ID,
        )

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": f"bearer {self._signer.token()}",
            "apns-topic": self._topic,
            "apns-push-type": "alert",
            "apns-priority": "10",
        }

    @staticmethod
    def _payload(title: str, body: str) -> str:
        return json.dumps({"aps": {"alert": {"title": title, "body": body}, "sound": "default"}})

    async def send(self, token: str, title: str, body: str) -> PushSendResult:
        url = f"https://{self._host}/3/device/{token}"
        try:
            # HTTP/2 is mandatory for APNs. A short-lived client per send keeps the
            # path simple; connection pooling can be layered later if volume grows.
            async with httpx.AsyncClient(http2=True, timeout=_REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(url, headers=self._headers(), content=self._payload(title, body))
        except httpx.HTTPError as e:
            # Log-and-swallow: a transport failure must not roll back the user tx.
            logger.warning("APNs send failed (transport) token=%s err=%s", token, e)
            return PushSendResult(delivered=False)

        if resp.status_code == 200:
            return PushSendResult(delivered=True)

        # 410 Unregistered: the app was uninstalled — reap the token upstream.
        if resp.status_code == 410:
            logger.info("APNs 410 Unregistered — token is dead, will be reaped: %s", token)
            return PushSendResult(delivered=False, unregistered=True)

        logger.warning("APNs send rejected token=%s status=%s body=%s", token, resp.status_code, resp.text)
        return PushSendResult(delivered=False)


def build_push_client(config: Config) -> BasePushClient:
    """Local no-op in dev/test (or when APNs creds are absent); real APNs in prod."""
    if config.ENV in {"development", "local", "testing"} or not config.APNS_KEY:
        return LocalPushClient()
    return APNsPushClient(config)
