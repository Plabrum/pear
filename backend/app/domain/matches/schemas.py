from __future__ import annotations

from app.domain.dating_profiles.enums import City, Interest
from app.platform.actions.schemas import ActionableList
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── GET /matches ─────────────────────────────────────────────────────────────


class MatchSummaryOther(BaseSchema):
    id: Sqid
    chosenName: str | None
    dateOfBirth: str | None
    age: int | None
    city: City | None
    bio: str | None
    interests: list[Interest]
    firstPhoto: str | None


class MatchSummary(ActionableList):
    matchId: Sqid
    createdAt: str
    hasMessages: bool
    other: MatchSummaryOther


MatchesResponse = list[MatchSummary]


# ── GET /matches/{matchId}/sheet ─────────────────────────────────────────────


class MatchSheetWinger(BaseSchema):
    id: Sqid
    chosenName: str | None


class MatchSheetWingNote(BaseSchema):
    note: str
    suggestedBy: Sqid | None
    winger: MatchSheetWinger | None


class MatchSheetPromptTemplate(BaseSchema):
    id: Sqid
    question: str


class MatchSheetPrompt(BaseSchema):
    id: Sqid
    answer: str
    template: MatchSheetPromptTemplate | None


class MatchSheet(BaseSchema):
    wingNote: MatchSheetWingNote | None
    prompts: list[MatchSheetPrompt]
