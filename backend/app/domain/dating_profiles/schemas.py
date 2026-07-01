from __future__ import annotations

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.profiles.enums import Gender
from app.platform.actions.schemas import Actionable
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid


class SwipeProfile(Actionable):
    """The single projection for the collapsed swipe read.

    Replaces the former DiscoverProfile / LikesYouProfile / WingProfile. The wire
    field names are preserved so the client read shapes stay recognizable: `photos`
    is the full approved-photo array (discover), `firstPhoto` is the first of them
    (likes-you / wing-pool), and the `wingNote` / `suggestedBy` / `suggesterName`
    trio carries the pending winger-suggestion (null in the winger context).
    """

    profileId: Sqid
    userId: Sqid
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
    suggestedBy: Sqid | None
    suggesterName: str | None


class LikesYouCountResponse(BaseSchema):
    count: int


# ── Action input shapes (the target dating profile is the URL object) ──────────


class SuggestActionData(BaseSchema):
    """Suggest body — the winger proposes a profile to one of their daters.

    The suggested (recipient) profile is the URL object, so only `daterId` (whose
    behalf the suggestion is made) and an optional hand-pick `note` are carried.
    Always creates a *pending* suggestion (decision NULL) the dater must act on.
    """

    daterId: Sqid
    note: str | None = None


class DeclineForDaterData(BaseSchema):
    """Decline-for-dater body — the winger passes on a profile on the dater's behalf.

    Records a `declined` decision so the profile leaves the dater's pool; the dater
    is not notified (nothing for them to act on). The declined (recipient) profile is
    the URL object, so only `daterId` is carried.
    """

    daterId: Sqid


class ReportActionData(BaseSchema):
    """Report body — only the reason; the reported profile is the URL object."""

    reason: str
