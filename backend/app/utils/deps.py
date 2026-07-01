import inspect
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any

from litestar import Request
from litestar.di import Provide
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

_registry: dict[str, Provide] = {}


def dep(name: str, *, sync_to_thread: bool = False) -> Callable:
    """Register a provider function as a named Litestar dependency."""

    def decorator(fn: Callable) -> Callable:
        is_async = inspect.iscoroutinefunction(fn) or inspect.isasyncgenfunction(fn)
        _registry[name] = Provide(fn) if is_async else Provide(fn, sync_to_thread=sync_to_thread)
        return fn

    return decorator


def get_dependencies() -> dict[str, Any]:
    return dict(_registry)


@asynccontextmanager
async def rls_transaction(db_session: AsyncSession, *, user_id: int | None) -> AsyncGenerator[AsyncSession]:
    """Open one transaction with Pear's RLS session variables set — the primitive
    behind every scoped DB unit of work.

    The connection already runs as the dedicated NON-superuser `pear_app` role
    (`ASYNC_DATABASE_URL`), so there is no `SET ROLE`: the role *is* the non-owner
    role from the moment the connection opens, and FORCE RLS applies natively. We
    only set the per-tx GUCs — both `SET LOCAL`, so they die with the transaction
    and cannot leak across pooled connections:

    * `app.is_system_mode = false` — the trusted-operation escape, defensively
      pinned off. Only the first-login bootstrap and system/worker jobs set it true.
    * `app.user_id` — the actor `public.current_user_id()` reads. `user_id=None`
      (an unauthenticated request) sets none, so RLS fails closed (policies
      comparing against `current_user_id()` deny).

    Used directly by long-lived handlers (e.g. WebSockets) that outlive a single
    transaction: a socket runs for minutes and would either hold one transaction
    open the whole time or break the request-scoped context manager by committing
    inside, so it wraps each unit of work in its own short-lived `rls_transaction`.
    """
    async with db_session.begin():
        await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
        if user_id is not None:
            await db_session.execute(text(f"SET LOCAL app.user_id = {int(user_id)}"))
        yield db_session


@dep("transaction")
async def provide_transaction(db_session: AsyncSession, request: Request) -> AsyncGenerator[AsyncSession]:
    """Request-scoped application of `rls_transaction`: one transaction per request,
    scoped to the authenticated principal.

    Pear has no organization concept — scope is relationship-based (dater <-> winger
    <-> match), so the only actor is `app.user_id`, sourced from the principal that
    SessionAuth's `retrieve_user_handler` put on `request.scope["user"]` after
    rehydrating it from the cookie session. Unauthenticated requests (login,
    magic-link) have no principal, so the actor is None and RLS fails closed.
    """
    user_id = int(request.user.id) if request.scope.get("user") is not None else None
    async with rls_transaction(db_session, user_id=user_id) as tx:
        yield tx
