from __future__ import annotations

from uuid import UUID

from msgspec import UNSET, UnsetType

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.decisions.enums import DecisionType
from app.domain.profiles.enums import Gender
from app.platform.base.schemas import BaseSchema


class SwipeProfile(BaseSchema):
    """The single projection for the collapsed swipe read.

    Replaces the former DiscoverProfile / LikesYouProfile / WingProfile. The wire
    field names are preserved so the client read shapes stay recognizable: `photos`
    is the full approved-photo array (discover), `firstPhoto` is the first of them
    (likes-you / wing-pool), and the `wingNote` / `suggestedBy` / `suggesterName`
    trio carries the pending winger-suggestion (null in the winger context).
    """

    profileId: UUID
    userId: UUID
    chosenName: str
    gender: Gender | None
    age: int
    city: City
    bio: str | None
    datingStatus: DatingStatus
    interests: list[Interest]
    photos: list[str]
    firstPhoto: str | None
    wingNote: str | None
    suggestedBy: UUID | None
    suggesterName: str | None


class LikesYouCountResponse(BaseSchema):
    count: int


# ── Action input shapes (the target dating profile is the URL object) ──────────


class SuggestActionData(BaseSchema):
    """Suggest body — the winger's dater + optional note/decision.

    The suggested (recipient) profile is the URL object, so only `daterId`
    (whose behalf the suggestion is made), an optional `note`, and an optional
    `decision` (`None` = a normal suggestion the dater must act on, `'declined'`
    = bypass the dater) are carried in the body.
    """

    daterId: UUID
    decision: DecisionType | None = None
    note: str | None | UnsetType = UNSET


class ReportActionData(BaseSchema):
    """Report body — only the reason; the reported profile is the URL object."""

    reason: str
