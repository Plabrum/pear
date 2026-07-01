"""Mutations for the profiles domain — all writes live here as registered actions.

Ported from the POST/PATCH handlers in
`supabase/functions/api/domains/profiles/route.ts`:

  * `UpdateProfile`        (PATCH /profiles/me)        -> BaseObjectAction[Profile]
  * `CreateDatingProfile`  (POST  /dating-profiles)    -> BaseTopLevelAction
  * `UpdateDatingProfile`  (PATCH /dating-profiles/me) -> BaseObjectAction[DatingProfile]

Each `execute` mutates the ORM directly under the request's RLS-scoped transaction;
the surrounding action machinery (see `app.platform.actions.base.ActionGroup.trigger`)
commits on return and rolls back on raise. User-facing failures are raised as typed
`ApplicationError` subclasses (404 / 409), reproducing the Hono `HTTPException`
status codes — never ad-hoc responses.

`dating_status` (open|break|winging) is updated here as a plain attribute. A full
state machine for it is intentionally NOT modeled (the doc marks it optional and
the transitions are trivial open<->break<->winging); discover/swipe gating that
*reads* `dating_status` lands with the discover/decisions domains.

Registration: this module is imported at boot by `discover_and_import([...],
base_path="app/domain")`, which runs `action_group_factory(...)` to register the
group + decorates each action class into the singleton `ActionRegistry`. The
`ActionGroupType.PROFILE_ACTIONS` / `DATING_PROFILE_ACTIONS` members are added to
`app.platform.actions.enums` (done here, as the template domain; other domains'
members are added by the Integrate stage).
"""

from __future__ import annotations

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
    "avatarUrl": "avatar_url",
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

profile_actions = action_group_factory(
    ActionGroupType.PROFILE_ACTIONS,
    default_invalidation="profiles",
    model_type=Profile,
)

dating_profile_actions = action_group_factory(
    ActionGroupType.DATING_PROFILE_ACTIONS,
    default_invalidation="dating_profiles",
    model_type=DatingProfile,
)


# ── PATCH /profiles/me ─────────────────────────────────────────────────────────


@profile_actions
class UpdateProfile(BaseObjectAction[Profile, UpdateProfileData]):
    action_key = "update"  # type: ignore[assignment]
    label = "Edit Profile"
    icon = ActionIcon.EDIT

    @classmethod
    def is_available(cls, obj: Profile, deps: ActionDeps) -> bool:
        # A user may only edit their own profile row (RLS also enforces this).
        return obj.id == deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: Profile,
        data: UpdateProfileData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        _apply(obj, fields_set(data), _PROFILE_FIELD_MAP)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Profile updated",
            invalidate_queries=["profiles"],
        )


# ── POST /dating-profiles (onboarding) ─────────────────────────────────────────


@dating_profile_actions
class CreateDatingProfile(BaseTopLevelAction[CreateDatingProfileData]):
    action_key = "create"  # type: ignore[assignment]
    label = "Create Dating Profile"
    icon = ActionIcon.ADD

    @classmethod
    async def execute(
        cls,
        data: CreateDatingProfileData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        existing = await fetch_dating_profile_base(transaction, deps.user.id)
        if existing is not None:
            raise DatingProfileAlreadyExistsError()

        provided = fields_set(data)
        dating_profile = DatingProfile(
            user_id=deps.user.id,
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
        if "datingStatus" in provided:
            dating_profile.dating_status = provided["datingStatus"]  # type: ignore[assignment]

        transaction.add(dating_profile)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Dating profile created",
            invalidate_queries=["dating_profiles"],
            created_id=dating_profile.id,
        )


# ── PATCH /dating-profiles/me ──────────────────────────────────────────────────


@dating_profile_actions
class UpdateDatingProfile(BaseObjectAction[DatingProfile, UpdateDatingProfileData]):
    action_key = "update"  # type: ignore[assignment]
    label = "Edit Dating Profile"
    icon = ActionIcon.EDIT

    @classmethod
    def is_available(cls, obj: DatingProfile, deps: ActionDeps) -> bool:
        # A user may only edit their own dating profile (RLS also enforces this).
        return obj.user_id == deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: UpdateDatingProfileData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        provided = fields_set(data)
        if not provided:
            # No-op PATCH — matches Hono's "updated: false" short-circuit, but the
            # row still exists, so it's not a 404.
            return ActionExecutionResponse(message="No changes")
        _apply(obj, provided, _DATING_PROFILE_FIELD_MAP)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Dating profile updated",
            invalidate_queries=["dating_profiles"],
        )
