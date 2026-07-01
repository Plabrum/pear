from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.schemas import (
    Match,
    MySuggestion,
    MySuggestionStatus,
    PendingSuggestion,
)
from app.domain.matches.models import Match as MatchModel


@dataclass
class SuggestionRow:
    id: UUID
    decision: DecisionType | None
    has_match: bool
    dater_id: UUID
    dater_name: str | None
    recipient_name: str | None
    created_at: datetime | None


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def match_to_dto(row: MatchModel) -> Match:
    return Match(
        id=row.id,
        userAId=row.user_a_id,
        userBId=row.user_b_id,
        createdAt=_iso(row.created_at),
    )


def row_to_pending_suggestion(
    *,
    suggestion_id,
    recipient_id,
    note: str | None,
    created_at: datetime | None,
    winger_id,
    winger_name: str | None,
) -> PendingSuggestion:
    return PendingSuggestion(
        id=suggestion_id,
        recipientId=recipient_id,
        note=note,
        createdAt=_iso(created_at),
        wingerId=winger_id,
        wingerName=winger_name,
    )


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
