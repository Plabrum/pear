import asyncio
import logging
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from functools import wraps
from typing import Any, cast

from litestar import Request
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.config import config
from app.platform.queue.enums import TaskName, TaskRoleType
from app.platform.queue.exceptions import CommittableTaskError
from app.platform.queue.registry import get_registry
from app.platform.queue.types import AppContext


def _quote_literal(value: str) -> str:
    """Single-quote a string for inlining into a SET LOCAL statement."""
    return "'" + value.replace("'", "''") + "'"


@asynccontextmanager
async def task_transaction(
    db_sessionmaker: async_sessionmaker[AsyncSession],
    role_type: TaskRoleType = TaskRoleType.SYSTEM,
    *,
    user_id: str | None = None,
) -> AsyncGenerator[AsyncSession]:
    """Async context manager that begins a transaction with RLS context.

    role_type=USER sets `app.user_id` so RLS policies scope to a single user
    (requires the `user_id` kwarg — a UUID string) and pins `app.is_system_mode =
    false`. role_type=SYSTEM runs trusted system-actor work with no user scope and
    `app.is_system_mode = true` (the honored RLS escape).

    The worker connection runs as the NON-superuser `pear_app` role
    (`ASYNC_DATABASE_URL`), so — like the request path — there is no `SET ROLE`:
    FORCE RLS applies natively and only the per-tx GUCs are set. `SET LOCAL` is
    transaction-scoped, so system mode cannot leak across pooled connections.

    Pear has no organization concept — scope is relationship-based (dater <->
    winger <-> match), so only `app.user_id` is set.

    Commits on success or on CommittableTaskError (then re-raises).
    Rolls back on all other exceptions.
    """
    async with db_sessionmaker() as session:
        await session.begin()
        try:
            if role_type == TaskRoleType.USER:
                if user_id is None:
                    raise ValueError("user_id is required for TaskRoleType.USER")
                await session.execute(text("SET LOCAL app.is_system_mode = false"))
                await session.execute(text(f"SET LOCAL app.user_id = {_quote_literal(user_id)}"))
            else:
                # SYSTEM jobs run as the trusted system actor: the honored escape.
                await session.execute(text("SET LOCAL app.is_system_mode = true"))
            yield session
            await session.commit()
        except CommittableTaskError:
            await session.commit()
            raise
        except Exception:
            await session.rollback()
            raise


def with_transaction(
    fn: Callable[..., Any] | None = None,
    *,
    role_type: TaskRoleType = TaskRoleType.SYSTEM,
) -> Callable[..., Any]:
    """Decorator that injects `transaction: AsyncSession` as a keyword argument.

    Args:
        role_type: RLS context for the transaction (default: SYSTEM).
            SYSTEM runs without a user scope. USER requires `user_id` (UUID str)
            in the task kwargs.

    If `transaction` is already present in kwargs (e.g. passed by dispatch_task in
    sync mode), the function is called directly — the caller owns the session lifecycle.

    Usage:
        @with_transaction                               # SYSTEM (default)
        @with_transaction(role_type=TaskRoleType.USER)  # USER — reads user_id from kwargs
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        async def wrapper(ctx: Any, **kwargs: Any) -> Any:
            if "transaction" in kwargs:
                return await func(ctx, **kwargs)
            user_id = kwargs.get("user_id") if role_type == TaskRoleType.USER else None
            async with task_transaction(ctx["db_sessionmaker"], role_type, user_id=user_id) as session:
                return await func(ctx, transaction=session, **kwargs)

        return wrapper

    # Support both @with_transaction and @with_transaction(role_type=...)
    if fn is not None:
        return decorator(fn)
    return decorator


async def dispatch_task(
    transaction: AsyncSession,
    request: Request,
    task_name: TaskName,
    *,
    queue: str = "default",
    **kwargs: Any,
) -> None:
    """Dispatch a task either inline (QUEUE_SYNC=true) or via the SAQ queue.

    In sync mode the task runs immediately, reusing the caller's session so no
    extra DB connection or commit is needed. If the task raises, the exception
    propagates and the outer transaction rolls back.

    In async mode the task is enqueued AFTER the session commits — registered via
    a one-shot SQLAlchemy `after_commit` listener so a rolled-back request never
    leaks a job onto the queue.
    """
    if config.QUEUE_SYNC:
        fn = get_registry().get_task_by_name(task_name)
        if fn is None:
            raise ValueError(f"No task registered for {task_name!r}")
        ctx = cast(AppContext, {"config": config})
        await fn(ctx, transaction=transaction, **kwargs)
    else:

        async def _enqueue() -> None:
            try:
                await request.app.state.task_queues.get(queue).enqueue(task_name, **kwargs)
            except Exception:
                logging.getLogger(__name__).exception("Failed to enqueue task %s", task_name)

        def _listener(_session: Any) -> None:
            asyncio.ensure_future(_enqueue())

        event.listen(transaction.sync_session, "after_commit", _listener, once=True)
