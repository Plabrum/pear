from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MissingRLSContextError(Exception):
    """Session has no user_id set — caller is outside an RLS context."""


async def current_user_id(transaction: AsyncSession) -> int:
    result = await transaction.execute(text("SELECT NULLIF(current_setting('app.user_id', true), '')::int"))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise MissingRLSContextError("app.user_id is not set on this session")
    return int(user_id)
