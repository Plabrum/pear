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

    TODO(Phase 4): Auth in this phase is a STUB — the user is derived from a decoded
    (but NOT signature-verified) JWT `sub`, mirroring the current Hono authMiddleware.
    Phase 4 replaces this with the self-hosted auth provider, verifies the token, and
    wires the real `role = authenticated` / RLS GUC enforcement. Until then the
    `SET LOCAL` calls below establish the contract the Phase-4 policies will read.
    """
    async with db_session.begin():
        # RLS floor: downgrade the connection's role for the duration of the request.
        await db_session.execute(text("SET LOCAL role = authenticated"))
        if request.scope.get("user") is not None:
            # `request.user.id` is a UUID string sourced from the decoded JWT `sub`.
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

    TODO(Phase 4): see `provide_transaction` — role/GUC enforcement is stubbed.
    """
    async with db_session.begin():
        await db_session.execute(text("SET LOCAL role = authenticated"))
        await db_session.execute(text(f"SET LOCAL app.user_id = {_quote_literal(user_id)}"))
        yield db_session
