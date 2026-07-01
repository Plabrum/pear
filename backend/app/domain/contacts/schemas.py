from __future__ import annotations

from uuid import UUID

from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender
from app.platform.base.schemas import BaseSchema

# ── Nested summaries ─────────────────────────────────────────────────────────


class WingerSummary(BaseSchema):
    id: UUID
    chosenName: str | None
    gender: Gender | None
    avatarUrl: str | None


class DaterSummary(BaseSchema):
    id: UUID
    chosenName: str | None


class WingingForDater(BaseSchema):
    id: UUID
    chosenName: str | None
    avatarUrl: str | None
    interests: list[Interest] | None
    bio: str | None


# ── Roster rows ──────────────────────────────────────────────────────────────


class Wingperson(BaseSchema):
    id: UUID
    createdAt: str
    winger: WingerSummary | None


class IncomingInvitation(BaseSchema):
    id: UUID
    createdAt: str
    dater: DaterSummary | None


class WingingForRow(BaseSchema):
    id: UUID
    createdAt: str
    dater: WingingForDater | None


class SentInvitation(BaseSchema):
    id: UUID
    createdAt: str
    phoneNumber: str
    winger: DaterSummary | None


# ── Combined GET /wingpeople response ────────────────────────────────────────


class WingpeopleResponse(BaseSchema):
    wingpeople: list[Wingperson]
    invitations: list[IncomingInvitation]
    wingingFor: list[WingingForRow]
    sentInvitations: list[SentInvitation]
    # contactId -> count of suggestions in the last 7 days.
    weeklyCounts: dict[str, int]


# ── GET /winger-tabs (the daters the caller wings for) ───────────────────────


class WingingForTab(BaseSchema):
    """The minimal `{id, name}` projection backing the winger-side dater tabs."""

    id: UUID
    name: str


WingingForTabsResponse = list[WingingForTab]


# ── Invite mutation (POST /wingpeople/invite) ────────────────────────────────


class InviteWingpersonData(BaseSchema):
    """POST /wingpeople/invite body."""

    phoneNumber: str


class InviteWingpersonResponse(BaseSchema):
    id: UUID
    phoneNumber: str
    wingerId: UUID | None
