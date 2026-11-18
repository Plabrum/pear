from __future__ import annotations

import msgspec
from msgspec import UNSET, UnsetType

from app.domain.dating_profiles.enums import City, DatingStatus, Interest, Religion
from app.domain.photos.enums import PhotoApprovalState
from app.domain.profiles.enums import Gender, UserRole
from app.domain.prompts.enums import ApprovalState
from app.platform.actions.schemas import Actionable, ActionableDetail
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── Base profile ─────────────────────────────────────────────────────────────


class Profile(ActionableDetail):
    id: Sqid
    chosenName: str | None
    avatarUrl: str | None
    phoneNumber: str | None
    dateOfBirth: str | None
    gender: Gender | None
    role: UserRole
    pushToken: str | None


class UpdateProfileData(BaseSchema):
    """PATCH /profiles/me body. Every field omittable; `UNSET` => leave as-is.

    `avatarMediaId` references a platform Media the caller created+uploaded via the
    media endpoints; the read paths resolve it to a public URL (`avatarUrl`)."""

    chosenName: str | UnsetType = UNSET
    dateOfBirth: str | None | UnsetType = UNSET
    phoneNumber: str | None | UnsetType = UNSET
    gender: Gender | None | UnsetType = UNSET
    pushToken: str | None | UnsetType = UNSET
    avatarMediaId: Sqid | None | UnsetType = UNSET


# ── Dating profile (own) ─────────────────────────────────────────────────────


class PromptResponseAuthor(BaseSchema):
    id: Sqid
    chosenName: str | None
    avatarUrl: str | None


class OwnPromptResponse(Actionable):
    id: Sqid
    message: str
    status: ApprovalState
    userId: Sqid
    createdAt: str
    author: PromptResponseAuthor | None


class PromptTemplateRef(BaseSchema):
    id: Sqid
    question: str


class OwnProfilePrompt(Actionable):
    id: Sqid
    answer: str
    createdAt: str
    template: PromptTemplateRef
    responses: list[OwnPromptResponse]


class PhotoSuggester(BaseSchema):
    id: Sqid
    chosenName: str | None


class OwnProfilePhoto(Actionable):
    id: Sqid
    storageUrl: str
    displayOrder: int
    status: PhotoApprovalState
    suggesterId: Sqid | None
    suggester: PhotoSuggester | None


class OwnDatingProfile(ActionableDetail):
    id: Sqid
    userId: Sqid
    bio: str | None
    city: City
    interestedGender: list[Gender]
    ageFrom: int
    ageTo: int | None
    religion: Religion
    religiousPreference: Religion | None
    interests: list[Interest]
    isActive: bool
    datingStatus: DatingStatus
    createdAt: str
    updatedAt: str
    photos: list[OwnProfilePhoto]
    prompts: list[OwnProfilePrompt]


# GET /dating-profiles/me returns the profile or null.
OwnDatingProfileResponse = OwnDatingProfile | None


class CreateDatingProfileData(BaseSchema):
    """POST /dating-profiles body (onboarding)."""

    city: City
    ageFrom: int
    interestedGender: list[Gender]
    religion: Religion
    interests: list[Interest]
    bio: str | UnsetType = UNSET
    ageTo: int | None | UnsetType = UNSET
    religiousPreference: Religion | None | UnsetType = UNSET
    datingStatus: DatingStatus | UnsetType = UNSET


class UpdateDatingProfileData(BaseSchema):
    """PATCH /dating-profiles/me body. Every field omittable; `UNSET` => leave as-is."""

    bio: str | None | UnsetType = UNSET
    city: City | UnsetType = UNSET
    ageFrom: int | UnsetType = UNSET
    ageTo: int | None | UnsetType = UNSET
    interestedGender: list[Gender] | UnsetType = UNSET
    religion: Religion | UnsetType = UNSET
    religiousPreference: Religion | None | UnsetType = UNSET
    interests: list[Interest] | UnsetType = UNSET
    isActive: bool | UnsetType = UNSET


# ── Public profile (any authenticated user can view) ─────────────────────────


class PublicProfilePhoto(BaseSchema):
    id: Sqid
    storageUrl: str
    displayOrder: int
    status: PhotoApprovalState
    suggesterId: Sqid | None


class PublicProfilePrompt(BaseSchema):
    id: Sqid
    answer: str
    createdAt: str
    template: PromptTemplateRef


class PublicDatingProfile(Actionable):
    id: Sqid
    bio: str | None
    city: City
    interests: list[Interest]
    religion: Religion
    photos: list[PublicProfilePhoto]
    prompts: list[PublicProfilePrompt]


class PublicProfile(ActionableDetail):
    id: Sqid
    chosenName: str | None
    avatarUrl: str | None
    datingProfile: PublicDatingProfile | None


def fields_set(data: msgspec.Struct) -> dict[str, object]:
    """Return only the explicitly-provided (non-UNSET) fields of an input struct.

    A PATCH only touches columns the caller actually sent. `None` is a real value
    (clear the column); `UNSET` means "absent — leave as-is".
    """
    out: dict[str, object] = {}
    for name in data.__struct_fields__:
        value = getattr(data, name)
        if value is not UNSET:
            out[name] = value
    return out
