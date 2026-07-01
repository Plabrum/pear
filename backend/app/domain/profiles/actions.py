from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from msgspec import UNSET
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.models import DatingProfile
from app.domain.profiles.exceptions import DatingProfileAlreadyExistsError
from app.domain.profiles.models import Profile
from app.domain.profiles.queries import fetch_dating_profile_base
from app.domain.profiles.schemas import (
    CreateDatingProfileData,
    UpdateDatingProfileData,
    UpdateProfileData,
    fields_set,
)
from app.platform.actions.base import (
    BaseObjectAction,
    BaseTopLevelAction,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from app.platform.auth.principal import User

# camelCase field name -> ORM (snake_case) attribute name. Only fields that
# differ from a naive lower-snake of the JSON key need listing; we map them all
# explicitly to keep the contract obvious.
_PROFILE_FIELD_MAP = {
    "chosenName": "chosen_name",
    "dateOfBirth": "date_of_birth",
    "phoneNumber": "phone_number",
    "gender": "gender",
    "role": "role",
    "pushToken": "push_token",
    "avatarMediaId": "avatar_media_id",
}

_DATING_PROFILE_FIELD_MAP = {
    "bio": "bio",
    "city": "city",
    "ageFrom": "age_from",
    "ageTo": "age_to",
    "interestedGender": "interested_gender",
    "religion": "religion",
    "religiousPreference": "religious_preference",
    "interests": "interests",
    "datingStatus": "dating_status",
    "isActive": "is_active",
}


def _apply(obj: object, provided: dict[str, object], field_map: dict[str, str]) -> None:
    """Assign each explicitly-provided camelCase field onto the ORM attribute."""
    for camel, value in provided.items():
        setattr(obj, field_map[camel], value)


# ── Action groups ─────────────────────────────────────────────────────────────


class ProfileActionKey(StrEnum):
    UPDATE = "update"


class DatingProfileActionKey(StrEnum):
    CREATE = "create"
    UPDATE = "update"


profile_actions = action_group_factory(
    ActionGroupType.PROFILE_ACTIONS,
    default_invalidation="/profiles",
    model_type=Profile,
)

dating_profile_actions = action_group_factory(
    ActionGroupType.DATING_PROFILE_ACTIONS,
    default_invalidation="/dating-profiles/me",
    model_type=DatingProfile,
)


# ── PATCH /profiles/me ─────────────────────────────────────────────────────────


@profile_actions
class UpdateProfile(BaseObjectAction[Profile, UpdateProfileData]):
    action_key: ClassVar[ProfileActionKey] = ProfileActionKey.UPDATE
    label = "Edit Profile"
    icon = ActionIcon.EDIT

    @classmethod
    def is_available(cls, obj: Profile, user: User, deps: ActionDeps) -> bool:
        # A user may only edit their own profile row (RLS also enforces this).
        return obj.id == user.id

    @classmethod
    async def execute(
        cls,
        obj: Profile,
        data: UpdateProfileData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        _apply(obj, fields_set(data), _PROFILE_FIELD_MAP)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Profile updated",
            invalidate_queries=["/profiles"],
        )


# ── POST /dating-profiles (onboarding) ─────────────────────────────────────────


@dating_profile_actions
class CreateDatingProfile(BaseTopLevelAction[CreateDatingProfileData]):
    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.CREATE
    label = "Create Dating Profile"
    icon = ActionIcon.ADD

    @classmethod
    async def execute(
        cls,
        data: CreateDatingProfileData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        existing = await fetch_dating_profile_base(transaction, user.id)
        if existing is not None:
            raise DatingProfileAlreadyExistsError()

        provided = fields_set(data)
        dating_profile = DatingProfile(
            user_id=user.id,
            city=provided["city"],
            bio=provided.get("bio"),
            age_from=provided["age_from"] if "age_from" in provided else data.ageFrom,
            age_to=provided.get("ageTo"),
            interested_gender=provided["interestedGender"],
            religion=provided["religion"],
            religious_preference=provided.get("religiousPreference"),
            interests=provided["interests"],
        )
        # datingStatus defaults to 'open' at the column level; honor it if supplied.
        # Narrow off the typed input field so the assignment is a real DatingStatus.
        if data.datingStatus is not UNSET:
            dating_profile.dating_status = data.datingStatus

        transaction.add(dating_profile)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Dating profile created",
            invalidate_queries=["/dating-profiles/me"],
            created_id=dating_profile.id,
        )


# ── PATCH /dating-profiles/me ──────────────────────────────────────────────────


@dating_profile_actions
class UpdateDatingProfile(BaseObjectAction[DatingProfile, UpdateDatingProfileData]):
    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.UPDATE
    label = "Edit Dating Profile"
    icon = ActionIcon.EDIT

    @classmethod
    def is_available(cls, obj: DatingProfile, user: User, deps: ActionDeps) -> bool:
        # A user may only edit their own dating profile (RLS also enforces this).
        return obj.user_id == user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: UpdateDatingProfileData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        provided = fields_set(data)
        if not provided:
            # No-op PATCH — the row still exists, so it's not a 404.
            return ActionExecutionResponse(message="No changes")
        _apply(obj, provided, _DATING_PROFILE_FIELD_MAP)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Dating profile updated",
            invalidate_queries=["/dating-profiles/me"],
        )
