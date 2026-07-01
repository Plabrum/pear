from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from app.config import Config

logger = logging.getLogger(__name__)

_TWILIO_BASE = "https://verify.twilio.com/v2/Services"


class OtpError(Exception):
    """Raised when the OTP provider rejects a send/check (caller maps to 4xx)."""


class BaseOtpClient(ABC):
    @abstractmethod
    async def send(self, phone: str) -> None:
        """Start a verification — send a code to the phone (E.164)."""

    @abstractmethod
    async def check(self, phone: str, code: str) -> bool:
        """Return True iff `code` is the valid current code for `phone`."""


class LocalOtpClient(BaseOtpClient):
    """Logs the 'send' and accepts a single fixed dev code — for dev and tests."""

    def __init__(self, dev_code: str = "000000"):
        self.dev_code = dev_code

    async def send(self, phone: str) -> None:
        logger.info("LOCAL OTP (not sent) -> phone=%s dev_code=%s", phone, self.dev_code)

    async def check(self, phone: str, code: str) -> bool:
        return code == self.dev_code


class TwilioOtpClient(BaseOtpClient):
    """Twilio Verify-backed OTP — delegates code gen/expiry/rate-limit to Twilio."""

    def __init__(self, config: Config):
        self.account_sid = config.TWILIO_ACCOUNT_SID
        self.auth_token = config.TWILIO_AUTH_TOKEN
        self.service_sid = config.TWILIO_VERIFY_SERVICE_SID

    async def send(self, phone: str) -> None:
        url = f"{_TWILIO_BASE}/{self.service_sid}/Verifications"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"To": phone, "Channel": "sms"},
                auth=(self.account_sid, self.auth_token),
            )
        if resp.status_code >= 400:
            raise OtpError(f"Twilio Verify send failed: {resp.status_code} {resp.text}")

    async def check(self, phone: str, code: str) -> bool:
        url = f"{_TWILIO_BASE}/{self.service_sid}/VerificationCheck"
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                data={"To": phone, "Code": code},
                auth=(self.account_sid, self.auth_token),
            )
        if resp.status_code >= 400:
            # 404 == no pending verification (expired / never sent) — treat as fail.
            return False
        return resp.json().get("status") == "approved"


def build_otp_client(config: Config) -> BaseOtpClient:
    """Local fake in local/testing; real Twilio Verify otherwise."""
    if config.ENV in {"development", "local", "testing"}:
        return LocalOtpClient(dev_code=config.DEV_OTP_CODE)
    return TwilioOtpClient(config)
