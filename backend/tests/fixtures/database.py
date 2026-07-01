import os
import random
import subprocess
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import TestConfig
from app.platform.base.models import BaseDBModel
from app.platform.base.rls_grants import APP_ROLE
from app.platform.base.rls_mixins import RLS_POLICY_REGISTRY

# Throwaway models that apply the RLS mixins. Importing them attaches their
# mappers + registers their mixin policies, so the test DB can build the tables and
# replay the exact policy SQL the mixins generate. Test-only, like SampleWidget.
from tests.fixtures.rls_mixin_domain.models import RlsOwnedThing, RlsWingThing  # noqa: F401

# Importing the sample model attaches its mapper to `BaseDBModel.metadata` so the
# `sample_widgets` table can be created in the TEST DB only. It lives under
# tests/fixtures/ (not app/domain/), so prod model discovery + Alembic
# autogenerate never see it and it is absent from the prod initial schema.
from tests.fixtures.sample_domain.models import SampleWidget  # noqa: F401

_BACKEND_DIR = Path(__file__).parent.parent.parent


def _admin_sync_url(test_config: TestConfig) -> str:
    """ADMIN_DB_URL is the bare `postgresql://` URL; pin psycopg v3 for SQLAlchemy."""
    return test_config.ADMIN_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)


def _ensure_app_role(conn, app_password: str) -> None:
    """Idempotently create the NON-superuser `pear_app` login role + set password.

    Roles are cluster-global, so this runs once as the owner before Alembic. The
    migration also bootstraps the role, but doing it here too makes the fixture
    self-sufficient on a bare cluster and keeps the password aligned with
    `ASYNC_DATABASE_URL`'s credentials.
    """
    conn.execute(
        text(
            f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname='{APP_ROLE}') "
            f"THEN CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE; END IF; END $$;"
        )
    )
    conn.execute(text(f"ALTER ROLE {APP_ROLE} PASSWORD '{app_password}'"))


def _reset_schema(conn, app_password: str) -> None:
    # Recreate public schema. The app connects as the NON-superuser `pear_app`
    # role (no SET ROLE anymore), so ensure that role exists before Alembic and
    # grant it schema access after recreation. The owner (`postgres`) retains ALL.
    conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
    conn.execute(text("CREATE SCHEMA public"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO postgres"))
    conn.execute(text("GRANT ALL ON SCHEMA public TO public"))
    _ensure_app_role(conn, app_password)
    conn.execute(text(f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}"))


def _build_mixin_table(conn, tablename: str, signature: str) -> None:
    """Create a mixin-backed test table, force RLS, apply its registered policy.

    Looks the policy up in `RLS_POLICY_REGISTRY` by (table, signature) so the SQL
    under test is the mixin's own output, then grants CRUD to `pear_app`.
    """
    BaseDBModel.metadata.create_all(bind=conn, tables=[BaseDBModel.metadata.tables[tablename]])
    conn.execute(text(f"ALTER TABLE public.{tablename} ENABLE ROW LEVEL SECURITY"))
    conn.execute(text(f"ALTER TABLE public.{tablename} FORCE ROW LEVEL SECURITY"))

    policy = next(p for p in RLS_POLICY_REGISTRY if p.on_entity == f"public.{tablename}" and p.signature == signature)
    conn.execute(text(f"CREATE POLICY {policy.signature} ON {policy.on_entity} {policy.definition}"))
    conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.{tablename} TO {APP_ROLE}"))


@pytest.fixture(scope="session")
def test_config() -> TestConfig:
    return TestConfig()


@pytest.fixture(scope="session")
def test_engine(test_config: TestConfig):
    """Engine the tests run against — connects as the NON-superuser `pear_app`.

    Because `pear_app` neither owns the tables nor is a superuser, RLS is
    genuinely enforced (FORCE RLS) — no bypass. This is the whole point of the
    non-superuser role model.
    """
    return create_async_engine(test_config.ASYNC_DATABASE_URL, echo=False, poolclass=NullPool)


@pytest.fixture(scope="session")
def setup_database(test_engine, test_config: TestConfig):
    """Drop schema, run Alembic migrations, yield, then clean up.

    Runs as the admin/owner (`ADMIN_DB_URL`). Ensures `pear_app` exists BEFORE
    Alembic (so the grants in the migrations have a role to grant to), runs
    `alembic upgrade head` (which also creates `pear_app` + grants idempotently),
    then re-grants schema privileges to `pear_app` after the schema recreation.
    """
    admin_engine = create_engine(_admin_sync_url(test_config), poolclass=NullPool)

    with admin_engine.begin() as conn:
        _reset_schema(conn, test_config.DB_APP_PASSWORD)

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
    # tables: the policy uses the same `is_system_mode() OR (user_id = me)` shape,
    # and CRUD is granted to the NON-superuser `pear_app` role the tests run as.
    with admin_engine.begin() as conn:
        BaseDBModel.metadata.create_all(
            bind=conn,
            tables=[BaseDBModel.metadata.tables[SampleWidget.__tablename__]],
        )
        conn.execute(text("ALTER TABLE public.sample_widgets ENABLE ROW LEVEL SECURITY"))
        conn.execute(text("ALTER TABLE public.sample_widgets FORCE ROW LEVEL SECURITY"))
        conn.execute(
            text(
                "CREATE POLICY user_scope_policy ON public.sample_widgets "
                "AS PERMISSIVE FOR ALL TO public USING ("
                "  public.is_system_mode()"
                "  OR (user_id = public.current_user_id()))"
            )
        )
        conn.execute(text(f"GRANT SELECT, INSERT, UPDATE, DELETE ON public.sample_widgets TO {APP_ROLE}"))

        # ── Test-only mixin-backed tables ────────────────────────────────────
        # Build each throwaway table and apply the *registered* mixin policy SQL
        # verbatim, so the test exercises exactly what the mixin generates rather
        # than a hand-copied predicate. Same RLS + grant shape as the prod tables.
        _build_mixin_table(conn, RlsOwnedThing.__tablename__, "user_scope_policy")
        _build_mixin_table(conn, RlsWingThing.__tablename__, "wingperson_scope_policy")

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
    it rolls back at the end of the test, undoing all changes. The connection is
    the NON-superuser `pear_app` role, so RLS is enforced; `app.is_system_mode =
    true` is the honored escape that lets factories/fixtures seed data freely
    (this is now a genuine bypass, not superuser-driven).
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
def user_id() -> int:
    """A stable random user id (int) for RLS-scoped fixtures.

    A high random int so it never collides with the small autoincrement ids the
    seed fixtures create.
    """
    return random.randint(1_000_000_000, 2_000_000_000)


@pytest.fixture
async def transaction(db_session: AsyncSession, user_id: int) -> AsyncGenerator[AsyncSession]:
    """Session with RLS enforced for `user_id`.

    Use instead of `db_session` to test user-scoped queries. Seed fixtures via
    `db_session` (system mode) before this takes effect. The connection is already
    the non-superuser `pear_app` role, so there is no `SET ROLE` — just establish
    the actor and turn the system escape off.
    """
    await db_session.execute(text(f"SET LOCAL app.user_id = {int(user_id)}"))
    await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
    yield db_session
