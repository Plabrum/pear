from __future__ import annotations

from typing import Literal

from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── My-suggestions read (suggestions I made as a winger) ───────────────────────

MySuggestionStatus = Literal["matched", "pending", "not_accepted"]


class MySuggestion(BaseSchema):
    """One card I suggested as a winger, with its computed status.

    The decision id is prefixed with `suggestion:` (see transformers), so `id` is a
    plain string, not a Sqid.
    """

    id: str
    daterId: Sqid
    daterName: str
    suggestedName: str
    status: MySuggestionStatus
    createdAt: str


MySuggestionsResponse = list[MySuggestion]
