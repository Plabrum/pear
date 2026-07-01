"""Auth request/response DTOs (msgspec structs — Litestar's native codec).

The wire contract uses camelCase to match the mobile client
(`accessToken`/`refreshToken`/`chosenName`). The token-core routes (refresh /
logout / me) live here; the login-method request shapes (OTP / Apple / magic
link) are added by the Methods agent in this same module.
"""

from __future__ import annotations

from uuid import UUID

import msgspec

from app.domain.profiles.enums import UserRole
from app.platform.auth.principal import User


class UserOut(msgspec.Struct, rename="camel"):
    """Serialized authenticated user: {id, role, chosenName}."""

    id: UUID
    role: UserRole | None
    chosen_name: str | None = None


class SessionOut(msgspec.Struct, rename="camel"):
    """A freshly issued session: access + refresh tokens + the user."""

    access_token: str
    refresh_token: str
    user: UserOut


class TokenPairOut(msgspec.Struct, rename="camel"):
    """A rotated token pair (no user payload — used by /auth/refresh)."""

    access_token: str
    refresh_token: str


class MeOut(msgspec.Struct, rename="camel"):
    """`GET /auth/me` envelope: {user}."""

    user: UserOut


class RefreshIn(msgspec.Struct, rename="camel"):
    refresh_token: str


class LogoutIn(msgspec.Struct, rename="camel"):
    refresh_token: str


# ── Login-method request shapes (OTP / Apple / magic link) ────────────────────


class OtpStartIn(msgspec.Struct, rename="camel"):
    """`POST /auth/otp/start` body: the E.164 phone to send a code to."""

    phone: str


class OtpCheckIn(msgspec.Struct, rename="camel"):
    """`POST /auth/otp/check` body: the phone + the code the user entered."""

    phone: str
    code: str


class AppleIn(msgspec.Struct, rename="camel"):
    """`POST /auth/apple` body: Apple's identity token (+ name on first grant)."""

    identity_token: str
    full_name: str | None = None


class MagicLinkRequestIn(msgspec.Struct, rename="camel"):
    """`POST /auth/magic-link/request` body: the email to send a login link to."""

    email: str


class MagicLinkVerifyIn(msgspec.Struct, rename="camel"):
    """`POST /auth/magic-link/verify` body: the one-time token from the email link."""

    token: str


def user_out_from_principal(user: User) -> UserOut:
    return UserOut(id=user.id, role=user.profile_role, chosen_name=user.chosen_name)
