from __future__ import annotations

from typing import Any

from email_validator import EmailNotValidError, validate_email
from litestar import Request, get, post
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.response import Redirect

from app.config import Config, config
from app.platform.auth.clients.apple import AppleAuthError, BaseAppleVerifier
from app.platform.auth.enums import AuthProvider
from app.platform.auth.magic_link import BaseMagicLinkStore
from app.platform.auth.rate_limit import BaseRateLimiter
from app.platform.auth.schemas import (
    AppleIn,
    MagicLinkRequestIn,
    MagicLinkVerifyIn,
    SessionOut,
)
from app.platform.auth.service import AuthService
from app.platform.comms.service.emails import EmailService


def _active_config(request: Request) -> Config:
    """The app's active config (shared via state) — TTLs, scheme, dev bypass email."""
    return getattr(request.app.state, "config", None) or config


def _client_ip(request: Request) -> str:
    """Best-effort caller IP for rate-limit keying (falls back to 'unknown')."""
    client = request.client
    return client.host if client is not None else "unknown"


def _normalize_email(raw: str) -> str:
    """Normalize an email for use as a stable identity subject. Raises on invalid."""
    try:
        return validate_email(raw, check_deliverability=False).normalized.lower()
    except EmailNotValidError as e:
        raise HTTPException(status_code=400, detail="Invalid email address") from e


# ── Apple Sign-In ─────────────────────────────────────────────────────────────


@post("/apple", exclude_from_auth=True)
async def apple_sign_in(
    data: AppleIn,
    apple_verifier: BaseAppleVerifier,
    auth_service: AuthService,
    request: Request,
) -> SessionOut:
    """Verify an Apple identity token and issue a session.

    Apple delivers email/name only on the FIRST authorization; `find_or_create_identity`
    persists them onto the profile when it creates it.
    """
    try:
        identity = await apple_verifier.verify(data.identity_token)
    except AppleAuthError as e:
        raise NotAuthorizedException("Invalid Apple identity token") from e

    profile, _created = await auth_service.find_or_create_identity(
        AuthProvider.APPLE,
        identity.subject,
        email=identity.email,
        name=data.full_name,
    )
    return await auth_service.issue_session(profile, device_info=_device_info(request))


# ── Magic link (email) ────────────────────────────────────────────────────────


@post("/magic-link/request", status_code=204, exclude_from_auth=True)
async def magic_link_request(
    data: MagicLinkRequestIn,
    magic_link_store: BaseMagicLinkStore,
    email_service: EmailService,
    rate_limiter: BaseRateLimiter,
    request: Request,
) -> None:
    """Mint a one-time token and email a login link. ALWAYS 204 (no existence leak).

    Dev bypass: when the email matches `config.DEV_MAGIC_LINK_EMAIL`, the token is
    still minted/stored but no mail is enqueued (so local/e2e can mint+verify a
    token without a mailbox — the test reads the token straight off the store).
    """
    cfg = _active_config(request)
    email = _normalize_email(data.email)

    if not await rate_limiter.allow(f"magic:{email}:{_client_ip(request)}"):
        raise HTTPException(status_code=429, detail="Too many sign-in requests; try again later")

    token = await magic_link_store.issue(email)

    # Dev bypass: skip the actual send for the configured dev address.
    if cfg.DEV_MAGIC_LINK_EMAIL and email == cfg.DEV_MAGIC_LINK_EMAIL.lower():
        return

    # The email link hits the GET verify hop, which 302s into the app scheme.
    verify_url = f"{cfg.API_BASE_URL}/auth/magic-link/verify?token={token}"
    await email_service.send_magic_link_email(
        to_email=email,
        magic_link_url=verify_url,
        expires_minutes=max(1, cfg.MAGIC_LINK_TTL_SECONDS // 60),
    )


@get("/magic-link/verify", exclude_from_auth=True)
async def magic_link_verify_redirect(token: str, request: Request) -> Redirect:
    """Email-link hop: 302 the browser into the app's deep-link scheme.

    Does NOT consume the token — the app extracts it and POSTs it back to the
    `verify` endpoint below. Keeps consumption a single, app-initiated step.
    """
    cfg = _active_config(request)
    target = f"{cfg.APP_DEEP_LINK_SCHEME}://magic-link?token={token}"
    return Redirect(path=target, status_code=302)


@post("/magic-link/verify", exclude_from_auth=True)
async def magic_link_verify(
    data: MagicLinkVerifyIn,
    magic_link_store: BaseMagicLinkStore,
    auth_service: AuthService,
    request: Request,
) -> SessionOut:
    """Consume a magic-link token once and issue a session for its email identity.

    Replay (already-consumed) and expired tokens both resolve to `None` from the
    store and are rejected with a 401.
    """
    email = await magic_link_store.consume(data.token)
    if email is None:
        raise NotAuthorizedException("Invalid or expired magic link")

    profile, _created = await auth_service.find_or_create_identity(AuthProvider.EMAIL, email)
    return await auth_service.issue_session(profile, device_info=_device_info(request))


def _device_info(request: Request) -> str | None:
    """Opaque device descriptor from the User-Agent (for session listing/auditing)."""
    ua = request.headers.get("User-Agent")
    return ua[:512] if ua else None


# Spread into `auth_router` in routes.py.
LOGIN_METHOD_ROUTES: list[Any] = [
    apple_sign_in,
    magic_link_request,
    magic_link_verify_redirect,
    magic_link_verify,
]
