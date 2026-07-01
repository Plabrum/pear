"""Request principal — the authenticated `User` dependency.

Phase 4 replaces the Phase-2 `StubUser` (decoded-but-unverified JWT) with a real
principal loaded from the `profiles` table after the access token's ES256
signature is verified. It still satisfies the structural `Actor` protocol
(`.id: UUID`, `.role: Role`) the state-machine / actions layers consume, and adds
`chosen_name` for the `/auth/me` + session `user` payload.

`Role` here is the state-machine caller role (DATER / WINGER / SYSTEM). The
profile's `UserRole` (dater | winger) maps onto it; a profile that has not yet
chosen a role during onboarding maps to DATER for transition purposes while the
serialized `user.role` stays `null` (see `serialize_user`).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.state_machine.roles import Role


@dataclass
class User:
    """Authenticated request principal, loaded from a verified access token."""

    id: UUID
    role: Role
    chosen_name: str | None = None
    # The profile's persisted dater|winger role (None until onboarding sets it).
    profile_role: UserRole | None = None

    @classmethod
    def from_profile(cls, profile: Profile) -> User:
        profile_role = profile.role
        transition_role = Role.WINGER if profile_role is UserRole.WINGER else Role.DATER
        return cls(
            id=profile.id,
            role=transition_role,
            chosen_name=profile.chosen_name,
            profile_role=profile_role,
        )
