"""SQLAlchemy reads for the winger-tabs domain.

Ported from `supabase/functions/api/domains/winger-tabs/queries.ts`. First arg is
always `db: AsyncSession`; no Litestar/msgspec imports. This is a join over the
viewer's *pending* winger-suggested cards (`decision IS NULL` and `suggested_by`
present), joined to the suggesting winger's profile, ordered newest-first. The
transformer then dedupes to distinct wingers.

RLS enforces *access* (the viewer only sees their own decisions); the explicit
`where` clause is for relevance.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.models import Decision
from app.domain.profiles.models import Profile


@dataclass
class WingerTabRow:
    id: UUID
    chosen_name: str | None
    created_at: datetime | None


async def fetch_winger_tabs(db: AsyncSession, dater_id: UUID) -> list[WingerTabRow]:
    """Wingers who have a pending suggestion for the viewer, newest first.

    Mirrors the Hono query: decisions where the viewer is the actor, the decision is
    still pending (NULL), and a `suggested_by` winger is present — joined to that
    winger's profile. Duplicates (a winger with several pending suggestions) are kept
    here and collapsed to distinct wingers in the transformer.
    """
    rows = (
        await db.execute(
            select(
                Profile.id,
                Profile.chosen_name,
                Decision.created_at,
            )
            .join(Profile, Profile.id == Decision.suggested_by)
            .where(
                and_(
                    Decision.actor_id == dater_id,
                    Decision.decision.is_(None),
                    Decision.suggested_by.is_not(None),
                )
            )
            .order_by(desc(Decision.created_at))
        )
    ).all()

    return [
        WingerTabRow(id=winger_id, chosen_name=chosen_name, created_at=created_at)
        for (winger_id, chosen_name, created_at) in rows
    ]
