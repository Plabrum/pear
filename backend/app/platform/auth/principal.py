from __future__ import annotations

from dataclasses import dataclass

from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.state_machine.roles import Role
from app.utils.sqids import Sqid


@dataclass
class User:
    """Authenticated request principal, loaded from a verified access token."""

    id: Sqid
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
