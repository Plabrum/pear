from __future__ import annotations

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.reports.models import ProfileReport
from app.utils.sqids import Sqid


async def insert_report(
    db: AsyncSession,
    reporter_id: Sqid,
    reported_id: Sqid,
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
    actor_id: Sqid,
    recipient_id: Sqid,
) -> None:
    """Upsert a `declined` decision so the reported profile leaves the queue.

    On conflict over (actor_id, recipient_id): if the reporter already has a
    decision row for the recipient (e.g. a stale like or a pending winger
    suggestion), it is overwritten to `'declined'`; otherwise a new declined row is
    inserted.
    """
    stmt = (
        pg_insert(Decision)
        .values(
            actor_id=actor_id,
            recipient_id=recipient_id,
            decision=DecisionType.DECLINED,
        )
        .on_conflict_do_update(
            constraint="unique_actor_recipient",
            set_={"decision": DecisionType.DECLINED},
        )
        .returning(Decision)
    )
    # populate_existing syncs the identity map so a same-transaction entity re-read
    # sees the declined decision (RETURNING refreshes the row we just wrote).
    await db.execute(stmt, execution_options={"populate_existing": True})
    await db.flush()
