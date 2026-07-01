from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.schemas import (
    MySuggestion,
    MySuggestionStatus,
)
from app.utils.sqids import Sqid


@dataclass
class SuggestionRow:
    id: Sqid
    decision: DecisionType | None
    has_match: bool
    dater_id: Sqid
    dater_name: str | None
    recipient_name: str | None
    created_at: datetime | None


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def transform_my_suggestion(row: SuggestionRow) -> MySuggestion:
    status: MySuggestionStatus
    if row.decision is DecisionType.DECLINED:
        status = "not_accepted"
    elif row.decision is DecisionType.APPROVED and row.has_match:
        status = "matched"
    else:
        status = "pending"
    return MySuggestion(
        # Prefix the decision id with `suggestion:` for a stable feed key.
        id=f"suggestion:{row.id}",
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        suggestedName=row.recipient_name or "",
        status=status,
        createdAt=_iso(row.created_at),
    )
