from __future__ import annotations

from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender
from app.platform.actions.schemas import ActionableList
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── Nested summaries ─────────────────────────────────────────────────────────


class WingerSummary(BaseSchema):
    id: Sqid
    chosenName: str | None
    gender: Gender | None
    avatarUrl: str | None


class DaterSummary(BaseSchema):
    id: Sqid
    chosenName: str | None


class WingingForDater(BaseSchema):
    id: Sqid
    chosenName: str | None
    avatarUrl: str | None
    interests: list[Interest] | None
    bio: str | None
    interestedGender: list[Gender] | None


# ── Roster rows ──────────────────────────────────────────────────────────────


class Wingperson(ActionableList):
    id: Sqid
    createdAt: str
    winger: WingerSummary | None


class IncomingInvitation(ActionableList):
    id: Sqid
    createdAt: str
    dater: DaterSummary | None


class WingingForRow(BaseSchema):
    id: Sqid
    createdAt: str
    dater: WingingForDater | None


class SentInvitation(ActionableList):
    id: Sqid
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

    id: Sqid
    name: str


WingingForTabsResponse = list[WingingForTab]


# ── Invite mutation (POST /wingpeople/invite) ────────────────────────────────


class InviteWingpersonData(BaseSchema):
    """POST /wingpeople/invite body."""

    phoneNumber: str


# ── Invite-token verify (GET/POST /invite/verify) ────────────────────────────


class InviteVerifyIn(BaseSchema):
    """POST /invite/verify body."""

    token: str


class InviteVerifyOut(BaseSchema):
    """Preview of an invite token's target contact — no mutation."""

    contactId: Sqid
    daterName: str | None
    alreadyLinked: bool


# ── Accept invite by token (a top-level CONTACT_ACTIONS action) ──────────────


class AcceptInviteByTokenData(BaseSchema):
    token: str
