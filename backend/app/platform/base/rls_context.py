"""Read the RLS session variables set by `provide_transaction` / `rls_transaction`.

The transaction wrappers `SET LOCAL app.user_id` so RLS policies evaluate
against the current actor. Non-route helpers (queries that need to set FK
columns) read it back here instead of plumbing the id through every signature.

Pear is relationship-scoped (dater <-> winger <-> match) — there is no
organization concept, so only `app.user_id` exists.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MissingRLSContextError(Exception):
    """Session has no user_id set — caller is outside an RLS context."""


async def current_user_id(transaction: AsyncSession) -> UUID:
    result = await transaction.execute(text("SELECT NULLIF(current_setting('app.user_id', true), '')"))
    user_id = result.scalar_one_or_none()
    if user_id is None:
        raise MissingRLSContextError("app.user_id is not set on this session")
    return UUID(str(user_id))
