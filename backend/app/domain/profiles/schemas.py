"""msgspec schemas for the profiles domain.

Ported from `supabase/functions/api/domains/profiles/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hooks
consume these. Enum-typed fields use the domain `Enum` classes directly; msgspec
serializes an Enum by its `.value`, which is exactly the wire format the Zod enums
emit (`'open'`, `'Boston'`, `'Male'`, …).

Output structs: `Profile` / `OwnDatingProfile` / `PublicProfile` (+ their nested
shapes). Input structs (consumed by the actions layer): `UpdateProfileData` /
`CreateDatingProfileData` / `UpdateDatingProfileData`. Inputs use `msgspec.UNSET`
for optional-and-omittable fields so a PATCH can distinguish "absent" (leave as-is)
from "explicitly null" (clear the column) — mirroring Hono's `.optional()` vs the
value being present.
"""

from __future__ import annotations

from uuid import UUID

import msgspec
from msgspec import UNSET, UnsetType

from app.domain.dating_profiles.enums import City, DatingStatus, Interest, Religion
from app.domain.profiles.enums import Gender, UserRole
from app.platform.base.schemas import BaseSchema

# ── Base profile ─────────────────────────────────────────────────────────────


class Profile(BaseSchema):
    id: UUID
    chosenName: str | None
    avatarUrl: str | None
    phoneNumber: str | None
    dateOfBirth: str | None
    gender: Gender | None
    role: UserRole
    pushToken: str | None


class UpdateProfileData(BaseSchema):
    """PATCH /profiles/me body. Every field omittable; `UNSET` => leave as-is."""

    chosenName: str | UnsetType = UNSET
    dateOfBirth: str | None | UnsetType = UNSET
    phoneNumber: str | None | UnsetType = UNSET
    gender: Gender | None | UnsetType = UNSET
    role: UserRole | UnsetType = UNSET
    pushToken: str | None | UnsetType = UNSET
    avatarUrl: str | None | UnsetType = UNSET


# ── Dating profile (own) ─────────────────────────────────────────────────────


class PromptResponseAuthor(BaseSchema):
    id: UUID
    chosenName: str | None
    avatarUrl: str | None


class OwnPromptResponse(BaseSchema):
    id: UUID
    message: str
    isApproved: bool
    userId: UUID
    createdAt: str
    author: PromptResponseAuthor | None


class PromptTemplateRef(BaseSchema):
    id: UUID
    question: str


class OwnProfilePrompt(BaseSchema):
    id: UUID
    answer: str
    createdAt: str
    template: PromptTemplateRef
    responses: list[OwnPromptResponse]


class PhotoSuggester(BaseSchema):
    id: UUID
    chosenName: str | None


class OwnProfilePhoto(BaseSchema):
    id: UUID
    storageUrl: str
    displayOrder: int
    approvedAt: str | None
    suggesterId: UUID | None
    suggester: PhotoSuggester | None


class OwnDatingProfile(BaseSchema):
    id: UUID
    userId: UUID
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
    ripeness: int


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


class CreateDatingProfileResponse(BaseSchema):
    id: UUID


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
    datingStatus: DatingStatus | UnsetType = UNSET
    isActive: bool | UnsetType = UNSET


# ── Public profile (any authenticated user can view) ─────────────────────────


class PublicProfilePhoto(BaseSchema):
    id: UUID
    storageUrl: str
    displayOrder: int
    approvedAt: str | None
    suggesterId: UUID | None


class PublicProfilePrompt(BaseSchema):
    id: UUID
    answer: str
    createdAt: str
    template: PromptTemplateRef


class PublicDatingProfile(BaseSchema):
    id: UUID
    bio: str | None
    city: City
    interests: list[Interest]
    religion: Religion
    photos: list[PublicProfilePhoto]
    prompts: list[PublicProfilePrompt]


class PublicProfile(BaseSchema):
    id: UUID
    chosenName: str | None
    avatarUrl: str | None
    datingProfile: PublicDatingProfile | None


def fields_set(data: msgspec.Struct) -> dict[str, object]:
    """Return only the explicitly-provided (non-UNSET) fields of an input struct.

    Mirrors the Hono queries' `if (fields.x !== undefined) set.x = …` pattern: a
    PATCH only touches columns the caller actually sent. `None` is a real value
    (clear the column); `UNSET` means "absent — leave as-is".
    """
    out: dict[str, object] = {}
    for name in data.__struct_fields__:
        value = getattr(data, name)
        if value is not UNSET:
            out[name] = value
    return out
