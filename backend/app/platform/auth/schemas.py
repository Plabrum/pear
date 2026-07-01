from __future__ import annotations

import msgspec

from app.domain.profiles.enums import UserRole
from app.platform.auth.principal import User
from app.utils.sqids import Sqid


class UserOut(msgspec.Struct, rename="camel"):
    """Serialized authenticated user: {id, role, chosenName}."""

    id: Sqid
    role: UserRole | None
    chosen_name: str | None = None


class MeOut(msgspec.Struct, rename="camel"):
    """`GET /auth/me` envelope: {user, hasDatingProfile}.

    `hasDatingProfile` lets the routing gate decide onboarding without a second
    fetch — it's the single session query's existence check.
    """

    user: UserOut
    has_dating_profile: bool = False


# ── Login-method request shapes (Apple / magic link) ──────────────────────────


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
