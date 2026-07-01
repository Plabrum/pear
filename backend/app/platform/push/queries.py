from __future__ import annotations

from typing import cast

from sqlalchemy import CursorResult, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.profiles.models import Profile


async def null_push_token(db: AsyncSession, token: str) -> int:
    """Null every `profiles.push_token` equal to `token`. Returns rows affected.

    Matches by value (not user id) so a token APNs reported as 410 Unregistered is
    cleared wherever it is stored. Must run under a system-mode transaction.
    """
    result = cast(
        CursorResult,
        await db.execute(update(Profile).where(Profile.push_token == token).values(push_token=None)),
    )
    return result.rowcount or 0
