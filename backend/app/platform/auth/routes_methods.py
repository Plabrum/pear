from __future__ import annotations

from typing import Any

from email_validator import EmailNotValidError, validate_email
from litestar import Request, get, post
from litestar.exceptions import HTTPException, NotAuthorizedException
from litestar.middleware.rate_limit import RateLimitConfig
from litestar.response import Redirect

from app.config import config
from app.domain.profiles.models import Profile
from app.platform.auth.clients.apple import AppleAuthError, BaseAppleVerifier
from app.platform.auth.enums import AuthProvider
from app.platform.auth.principal import User
from app.platform.auth.schemas import (
    AppleIn,
    MagicLinkRequestIn,
    MagicLinkVerifyIn,
    UserOut,
    user_out_from_principal,
)
from app.platform.auth.service import AuthService
from app.platform.comms.service.emails import EmailService


def _start_session(request: Request, profile: Profile) -> UserOut:
    """Set the cookie session for `profile` and return its serialized user.

    The session payload is the minimal `{"user_id": <int>}`; the request's
    principal is rehydrated from it on subsequent requests by the SessionAuth
    `retrieve_user_handler`.
    """
    request.set_session({"user_id": int(profile.id)})
    return user_out_from_principal(User.from_profile(profile))


# Per-route rate limit on magic-link minting: 3 requests/minute, keyed on caller IP
# (Litestar's `get_remote_address` default). Counters live in the app's in-memory
# "rate_limit" store — no Redis, no DI, no custom limiter.
_magic_link_rate_limit = RateLimitConfig(rate_limit=("minute", 3))


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
) -> UserOut:
    """Verify an Apple identity token and start a cookie session.

    Apple delivers email/name only on the FIRST authorization; `find_or_create_identity`
    persists them onto the profile when it creates it. On success the session cookie
    is set (Set-Cookie) and the user is returned — no tokens.
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
    return _start_session(request, profile)


# ── Magic link (email) ────────────────────────────────────────────────────────


@post(
    "/magic-link/request",
    status_code=204,
    exclude_from_auth=True,
    middleware=[_magic_link_rate_limit.middleware],
)
async def magic_link_request(
    data: MagicLinkRequestIn,
    auth_service: AuthService,
    email_service: EmailService,
) -> None:
    """Mint a one-time token and email a login link. ALWAYS 204 (no existence leak).

    Rate-limited per caller IP by `_magic_link_rate_limit` middleware (3/min). The
    raw token is put into the emailed link and never persisted — only its hash is
    stored (`AuthService.issue_magic_link`). In dev the `LocalEmailClient` logs the
    link rather than sending, so the token is recoverable from the email body.
    """
    email = _normalize_email(data.email)

    token = await auth_service.issue_magic_link(email)

    # The email link hits the GET verify hop, which 302s into the app scheme.
    verify_url = f"{config.API_BASE_URL}/auth/magic-link/verify?token={token}"
    await email_service.send_magic_link_email(
        to_email=email,
        magic_link_url=verify_url,
        expires_minutes=max(1, config.MAGIC_LINK_TTL_SECONDS // 60),
    )


@get("/magic-link/verify", exclude_from_auth=True)
async def magic_link_verify_redirect(token: str) -> Redirect:
    """Email-link hop: 302 the browser into the app's deep-link scheme.

    Does NOT consume the token — the app extracts it and POSTs it back to the
    `verify` endpoint below. Keeps consumption a single, app-initiated step.
    """
    target = f"{config.APP_DEEP_LINK_SCHEME}://magic-link?token={token}"
    return Redirect(path=target, status_code=302)


@post("/magic-link/verify", exclude_from_auth=True)
async def magic_link_verify(
    data: MagicLinkVerifyIn,
    auth_service: AuthService,
    request: Request,
) -> UserOut:
    """Consume a magic-link token once and start a cookie session for its identity.

    Replay (already-consumed) and expired tokens both resolve to `None` and are
    rejected with a 401. On success the session cookie is set (Set-Cookie) and the
    user is returned — no tokens.
    """
    email = await auth_service.consume_magic_link(data.token)
    if email is None:
        raise NotAuthorizedException("Invalid or expired magic link")

    profile, _created = await auth_service.find_or_create_identity(AuthProvider.EMAIL, email)
    return _start_session(request, profile)


# Spread into `auth_router` in routes.py.
LOGIN_METHOD_ROUTES: list[Any] = [
    apple_sign_in,
    magic_link_request,
    magic_link_verify_redirect,
    magic_link_verify,
]
