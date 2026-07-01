from __future__ import annotations

from typing import Literal
from uuid import UUID

import msgspec
from msgspec import UNSET

from app.platform.base.schemas import BaseSchema

# ── Output shapes ────────────────────────────────────────────────────────────


class Match(BaseSchema):
    id: UUID
    userAId: UUID
    userBId: UUID
    createdAt: str


class PendingSuggestion(BaseSchema):
    id: UUID
    recipientId: UUID
    note: str | None
    createdAt: str
    wingerId: UUID | None
    wingerName: str | None


# GET /decisions/pending-suggestions returns an array of PendingSuggestion.
PendingSuggestionsResponse = list[PendingSuggestion]


# ── My-suggestions read (suggestions I made as a winger) ───────────────────────

MySuggestionStatus = Literal["matched", "pending", "not_accepted"]


class MySuggestion(BaseSchema):
    """One card I suggested as a winger, with its computed status.

    The decision id is prefixed with `suggestion:` (see transformers), so `id` is a
    plain string, not a UUID.
    """

    id: str
    daterId: UUID
    daterName: str
    suggestedName: str
    status: MySuggestionStatus
    createdAt: str


MySuggestionsResponse = list[MySuggestion]


# ── Shared helper ──────────────────────────────────────────────────────────────


def fields_set(data: msgspec.Struct) -> dict[str, object]:
    """Return only the explicitly-provided (non-UNSET) fields of an input struct."""
    out: dict[str, object] = {}
    for name in data.__struct_fields__:
        value = getattr(data, name)
        if value is not UNSET:
            out[name] = value
    return out
