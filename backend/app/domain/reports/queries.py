from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.reports.models import ProfileReport


async def insert_report(
    db: AsyncSession,
    reporter_id: UUID,
    reported_id: UUID,
    reason: str,
) -> ProfileReport:
    """Record a report of `reported_id` by `reporter_id`."""
    report = ProfileReport(
        reporter_id=reporter_id,
        reported_id=reported_id,
        reason=reason,
    )
    db.add(report)
    await db.flush()
    return report


async def upsert_decline_decision(
    db: AsyncSession,
    actor_id: UUID,
    recipient_id: UUID,
) -> None:
    """Upsert a `declined` decision so the reported profile leaves the queue.

    On conflict over (actor_id, recipient_id): if the reporter already has a
    decision row for the recipient (e.g. a stale like or a pending winger
    suggestion), it is overwritten to `'declined'`; otherwise a new declined row is
    inserted.
    """
    existing = (
        await db.execute(
            select(Decision)
            .where(
                and_(
                    Decision.actor_id == actor_id,
                    Decision.recipient_id == recipient_id,
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.decision = DecisionType.DECLINED
    else:
        db.add(
            Decision(
                actor_id=actor_id,
                recipient_id=recipient_id,
                decision=DecisionType.DECLINED,
            )
        )
    await db.flush()
