from __future__ import annotations

from uuid import UUID

import msgspec
from msgspec import UNSET, UnsetType

from app.domain.decisions.enums import DecisionType
from app.platform.base.schemas import BaseSchema

# ── Output shapes ────────────────────────────────────────────────────────────


class Match(BaseSchema):
    id: UUID
    userAId: UUID
    userBId: UUID
    createdAt: str


class DirectDecisionResponse(BaseSchema):
    """POST /decisions success body."""

    created: bool
    match: Match | None


class ActSuggestionResponse(BaseSchema):
    """POST /decisions/suggestions/act success body."""

    match: Match | None


class SuggestResponse(BaseSchema):
    """POST /decisions/suggestions success body."""

    ok: bool


class PendingSuggestion(BaseSchema):
    id: UUID
    recipientId: UUID
    note: str | None
    createdAt: str
    wingerId: UUID | None
    wingerName: str | None


# GET /decisions/pending-suggestions returns an array of PendingSuggestion.
PendingSuggestionsResponse = list[PendingSuggestion]


# ── Action input shapes ──────────────────────────────────────────────────────


class DirectDecisionData(BaseSchema):
    """POST /decisions body — a dater's own like/pass on a recipient."""

    recipientId: UUID
    decision: DecisionType


class ActSuggestionData(BaseSchema):
    """POST /decisions/suggestions/act body — act on a pending winger suggestion."""

    recipientId: UUID
    decision: DecisionType


class SuggestData(BaseSchema):
    """POST /decisions/suggestions body — a winger creates a suggestion.

    `decision` is `None` for a normal suggestion the dater must act on, or
    `'declined'` to bypass the dater entirely (the only non-null literal
    accepted). `note` is optional/omittable.
    """

    daterId: UUID
    recipientId: UUID
    decision: DecisionType | None = None
    note: str | None | UnsetType = UNSET


def fields_set(data: msgspec.Struct) -> dict[str, object]:
    """Return only the explicitly-provided (non-UNSET) fields of an input struct."""
    out: dict[str, object] = {}
    for name in data.__struct_fields__:
        value = getattr(data, name)
        if value is not UNSET:
            out[name] = value
    return out
