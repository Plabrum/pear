"""Session-level filter that hides soft-deleted rows from all SELECT queries.

Applies `deleted_at IS NULL` to every `BaseDBModel` (and its aliases, including
relationship eager-loads) on the synchronous session class backing
`AsyncSession`. Opt out per-query by passing
`execution_options={"include_deleted": True}`.
"""

from typing import Any

from sqlalchemy import event, orm
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.base.models import BaseDBModel


def _soft_delete_filter(execute_state: Any) -> None:
    if not execute_state.is_select:
        return
    if execute_state.execution_options.get("include_deleted", False):
        return
    execute_state.statement = execute_state.statement.options(
        orm.with_loader_criteria(
            BaseDBModel,
            lambda cls: cls.deleted_at.is_(None),
            include_aliases=True,
        )
    )


def install_soft_delete_filter() -> None:
    event.listen(AsyncSession.sync_session_class, "do_orm_execute", _soft_delete_filter)
