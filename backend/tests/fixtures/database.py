"""Database fixtures with savepoint-based test isolation.

Adapted from sloopquest. Pear has NO organization concept, so the org GUC is
dropped — only `app.user_id` / `app.is_system_mode` are set. Each test runs
inside a SAVEPOINT on a connection that never commits; teardown rolls it back,
leaving the schema clean (faster than truncating and avoids migration-state
pollution).
"""

import os
import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import TestConfig
from app.platform.base.models import BaseDBModel

# Importing the sample model attaches its mapper to `BaseDBModel.metadata` so the
# `sample_widgets` table can be created in the TEST DB only. It lives under
# tests/fixtures/ (not app/domain/), so prod model discovery + Alembic
# autogenerate never see it and it is absent from the prod initial migration.
from tests.fixtures.sample_domain.models import SampleWidget  # noqa: F401

_BACKEND_DIR = Path(__file__).parent.parent.parent


def _admin_sync_url(test_config: TestConfig) -> str:
    """ADMIN_DB_URL is the bare `postgresql://` URL; pin psycopg v3 for SQLAlchemy."""
    return test_config.ADMIN_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def _reset_schema(conn) -> None:
    # Recreate public schema and ensure the `authenticated` role exists — the
    # request/test transaction does `SET LOCAL role = authenticated` (RLS floor).
    conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    conn.execute(
        text(
            "DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') "
            "THEN CREATE ROLE authenticated NOLOGIN; END IF; END $$;"
        )
    )
    conn.execute(text("GRANT authenticated TO postgres"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO authenticated"))


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    return TestConfig()


@pytest.fixture(scope="session")
def test_engine(test_config: TestConfig):
    return create_async_engine(test_config.ASYNC_DATABASE_URL, echo=False, poolclass=NullPool)


@pytest.fixture(scope="session")
def setup_database(test_engine, test_config: TestConfig):
    """Drop schema, run Alembic migrations, yield, then clean up."""
    admin_engine = create_engine(_admin_sync_url(test_config), poolclass=NullPool)

    with admin_engine.begin() as conn:
        _reset_schema(conn)

    result = subprocess.run(
        ["uv", "run", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        capture_output=True,
        text=True,
        env={**os.environ, "ENV": "testing"},
    )
    if result.returncode != 0:
        raise RuntimeError(f"Alembic migration failed:\n{result.stdout}\n{result.stderr}")

    # ── Test-only `sample_widgets` table ─────────────────────────────────────
    # The sample model lives outside app/, so Alembic never creates its table.
    # Build it here (against the admin engine) for the actions/state-machine
    # fixtures, mirroring the RLS + grants the prod migration applies to real
    # tables. This keeps the prod initial migration free of any sample artifacts.
    with admin_engine.begin() as conn:
        BaseDBModel.metadata.create_all(
            bind=conn,
            tables=[BaseDBModel.metadata.tables[SampleWidget.__tablename__]],
        )
        conn.execute(text("ALTER TABLE public.sample_widgets ENABLE ROW LEVEL SECURITY"))
        conn.execute(
            text(
                "CREATE POLICY user_scope_policy ON public.sample_widgets "
                "AS PERMISSIVE FOR ALL USING ("
                "  NULLIF(current_setting('app.is_system_mode', true), '')::boolean IS TRUE"
                "  OR (NULLIF(current_setting('app.user_id', true), '') IS NOT NULL"
                "      AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid))"
            )
        )
        conn.execute(
            text(
                "DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname='authenticated') "
                "THEN GRANT SELECT, INSERT, UPDATE, DELETE ON public.sample_widgets TO authenticated; "
                "END IF; END $$;"
            )
        )

    yield

    with admin_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
        conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    admin_engine.dispose()


@pytest.fixture
async def db_session(test_engine, setup_database) -> AsyncGenerator[AsyncSession]:
    """Function-scoped session in system mode for fixture creation.

    Each test runs inside a SAVEPOINT. The outer transaction is never committed —
    it rolls back at the end of the test, undoing all changes. System mode
    bypasses RLS so factories/fixtures can seed data freely.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()

    await connection.execute(text("SET LOCAL app.is_system_mode = true"))

    session = async_sessionmaker(
        bind=connection,
        expire_on_commit=False,
        autoflush=False,
        join_transaction_mode="create_savepoint",
    )()

    try:
        yield session
    finally:
        await session.close()
        await transaction.rollback()
        await connection.close()


@pytest.fixture
def user_id() -> str:
    """A stable random user id (UUID str) for RLS-scoped fixtures."""
    return str(uuid4())


@pytest.fixture
async def transaction(db_session: AsyncSession, user_id: str) -> AsyncGenerator[AsyncSession]:
    """Session with RLS enforced for `user_id`.

    Use instead of `db_session` to test user-scoped queries. Seed fixtures via
    `db_session` (system mode) before this takes effect.
    """
    await db_session.execute(text(f"SET LOCAL app.user_id = '{user_id}'"))
    await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
    yield db_session
