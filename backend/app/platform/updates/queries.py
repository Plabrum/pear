from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.updates.enums import RolloutStatus, UpdateChannel, UpdatePlatform
from app.platform.updates.models import AppUpdate


async def latest_relevant_update(
    transaction: AsyncSession,
    *,
    runtime_version: str,
    channel: UpdateChannel,
    platform: UpdatePlatform,
) -> AppUpdate | None:
    """The newest non-paused row for this (runtime_version, channel, platform).

    `PAUSED` rows are skipped entirely (falls through to an older `LIVE` row, if
    any) — a pause is "don't serve this one," not "kill the client's current
    update," which is what `ROLLED_BACK` is for.
    """
    stmt = (
        select(AppUpdate)
        .where(
            AppUpdate.runtime_version == runtime_version,
            AppUpdate.channel == channel,
            AppUpdate.platform == platform,
            AppUpdate.rollout.in_([RolloutStatus.LIVE, RolloutStatus.ROLLED_BACK]),
        )
        .order_by(AppUpdate.created_at.desc())
        .limit(1)
    )
    return (await transaction.execute(stmt)).scalar_one_or_none()
