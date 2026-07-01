"""Dependency registry for Litestar DI.

Decorate provider functions with @dep("key") to register them.
In factory.py, call discover_and_import(["deps.py"]) then get_dependencies().

Example:
    @dep("my_service")
    def provide_my_service(transaction: AsyncSession) -> MyService:
        return MyService(transaction)
"""

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


def _quote_literal(value: str) -> str:
    """Single-quote a string for inlining into a SET LOCAL statement."""
    return "'" + value.replace("'", "''") + "'"


@dep("transaction")
async def provide_transaction(db_session: AsyncSession, request: Request) -> AsyncGenerator[AsyncSession]:
    """Provide a request-scoped DB transaction with RLS session variables set.

    Pear has no organization concept — scope is relationship-based (dater <-> winger
    <-> match), so only `app.user_id` is set, sourced from the authenticated user's id.

    The connection already runs as the dedicated NON-superuser `pear_app` role
    (`ASYNC_DATABASE_URL`), so there is no per-request `SET ROLE`: the role *is* the
    non-superuser, non-owner role from the moment the connection is opened, and
    FORCE RLS applies natively. We only set the per-request GUCs:

    * `app.user_id` — the verified-token `sub` (a UUID), put on
      `request.scope["user"]` by the ES256 auth middleware *after* verifying the
      token's signature/exp/iss/aud. `public.current_user_id()` reads it.
      Unauthenticated requests set none, so RLS fails closed (policies comparing
      against `current_user_id()` deny).
    * `app.is_system_mode = false` — defensively pinned off for ordinary requests.
      Only the `AuthService` first-login bootstrap and system/worker jobs ever set
      it true. `SET LOCAL` is transaction-scoped, so it cannot leak across pooled
      connections; this is belt-and-suspenders against a stale GUC.
    """
    async with db_session.begin():
        # Trusted-operation escape is OFF for ordinary requests (tx-scoped).
        await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
        if request.scope.get("user") is not None:
            # `request.user.id` is the verified-token `sub` (a UUID).
            user_id = str(request.user.id)
            await db_session.execute(text(f"SET LOCAL app.user_id = {_quote_literal(user_id)}"))
        yield db_session


@asynccontextmanager
async def rls_transaction(db_session: AsyncSession, *, user_id: str) -> AsyncGenerator[AsyncSession]:
    """Short-lived RLS-scoped transaction for long-running handlers (e.g. WebSockets).

    The request-scoped `transaction` dep wraps the entire request in a single
    `db_session.begin()` context. Long-lived handlers run for minutes and would
    either hold one transaction open the whole time or break that context manager
    by committing inside. Use this helper to wrap each unit of work in its own
    short-lived transaction with the RLS session variables set.

    Like `provide_transaction`, the connection is already the non-superuser
    `pear_app` role, so no `SET ROLE` is needed — just the per-tx GUCs.
    """
    async with db_session.begin():
        await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
        await db_session.execute(text(f"SET LOCAL app.user_id = {_quote_literal(user_id)}"))
        yield db_session
