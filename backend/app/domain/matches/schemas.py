"""msgspec schemas for the matches domain.

Ported from `supabase/functions/api/domains/matches/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hooks
consume these. Enum-typed fields (`city`, `interests`) use the dating-profile
`Enum` classes directly; msgspec serializes an Enum by its `.value`, exactly the
Zod wire form (`'Boston'`, `'Travel'`, …).

Output structs:
  * `MatchSummary` (+ `MatchSummaryOther`)  — GET /matches list item.
  * `MatchSheet` (+ wing-note/prompt nested) — GET /matches/{matchId}/sheet.

There are no input structs: the matches domain is read-only (matches are created by
the decisions domain's match-formation side-effect, not by a matches mutation).
"""

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
