from __future__ import annotations

from uuid import UUID

from app.domain.dating_profiles.enums import City, Interest
from app.platform.base.schemas import BaseSchema

# ── GET /matches ─────────────────────────────────────────────────────────────


class MatchSummaryOther(BaseSchema):
    id: UUID
    chosenName: str | None
    dateOfBirth: str | None
    age: int | None
    city: City | None
    bio: str | None
    interests: list[Interest]
    firstPhoto: str | None


class MatchSummary(BaseSchema):
    matchId: UUID
    createdAt: str
    hasMessages: bool
    other: MatchSummaryOther


MatchesResponse = list[MatchSummary]


# ── GET /matches/{matchId}/sheet ─────────────────────────────────────────────


class MatchSheetWinger(BaseSchema):
    id: UUID
    chosenName: str | None


class MatchSheetWingNote(BaseSchema):
    note: str
    suggestedBy: UUID | None
    winger: MatchSheetWinger | None


class MatchSheetPromptTemplate(BaseSchema):
    id: UUID
    question: str


class MatchSheetPrompt(BaseSchema):
    id: UUID
    answer: str
    template: MatchSheetPromptTemplate | None


class MatchSheet(BaseSchema):
    wingNote: MatchSheetWingNote | None
    prompts: list[MatchSheetPrompt]
