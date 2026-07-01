from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

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
