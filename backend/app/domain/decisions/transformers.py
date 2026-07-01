"""snake_case ORM rows -> camelCase msgspec structs for the decisions domain.

Ported from `supabase/functions/api/domains/decisions/transformers.ts`. Maps the
SQLAlchemy `Match` ORM object onto the `Match` response struct, and the pending
suggestion read rows (a `Decision` joined to the suggesting winger's profile name)
onto `PendingSuggestion`. Datetime columns render as ISO-8601 strings to match the
Postgres `timestamptz`->JSON contract the mobile app already consumes.
"""

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
