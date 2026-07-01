from __future__ import annotations

from datetime import datetime

from app.domain.decisions.schemas import Match, PendingSuggestion
from app.domain.matches.models import Match as MatchModel


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
