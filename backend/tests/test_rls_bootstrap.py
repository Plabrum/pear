from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TestConfig
from app.domain.profiles.models import Profile
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity
from app.platform.auth.service import AuthService
from app.platform.auth.tokens import TokenService

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


async def test_first_login_bootstrap_succeeds_in_system_mode_without_actor(
    db_session: AsyncSession, test_config: TestConfig
) -> None:
    """As `pear_app`, system mode + NO app.user_id -> AuthService bootstraps identity.

    Mirrors the unauthenticated login route: there is no `app.user_id` yet, so the
    write would fail closed *except* for the honored `is_system_mode()` escape that
    `AuthService.find_or_create_identity` turns on. We first clear any fixture GUCs
    so it is unambiguously AuthService's own escape — not a leftover setting — that
    enables the writes.
    """
    # Start from the true unauthenticated bootstrap condition: escape OFF, no actor.
    await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
    await db_session.execute(text("SET LOCAL app.user_id = ''"))

    before_profiles = (await db_session.execute(select(func.count()).select_from(Profile))).scalar_one()
    before_identities = (await db_session.execute(select(func.count()).select_from(AuthIdentity))).scalar_one()

    service = AuthService(db_session, test_config, TokenService(db=db_session, config=test_config))
    subject = f"+1{uuid4().int % 10_000_000_000:010d}"

    profile, created = await service.find_or_create_identity(AuthProvider.PHONE, subject)

    assert created is True
    assert profile.id is not None

    # The profile + identity rows are genuinely persisted (visible in this tx).
    after_profiles = (await db_session.execute(select(func.count()).select_from(Profile))).scalar_one()
    after_identities = (await db_session.execute(select(func.count()).select_from(AuthIdentity))).scalar_one()
    assert after_profiles == before_profiles + 1
    assert after_identities == before_identities + 1

    identity = (
        await db_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.PHONE,
                AuthIdentity.provider_subject == subject,
            )
        )
    ).scalar_one()
    assert identity.profile_id == profile.id

    # Idempotent: a second call resolves the SAME profile without creating rows.
    profile2, created2 = await service.find_or_create_identity(AuthProvider.PHONE, subject)
    assert created2 is False
    assert profile2.id == profile.id


async def test_raw_profile_insert_denied_without_system_mode_or_actor(db_session: AsyncSession) -> None:
    """As `pear_app`, escape OFF + NO app.user_id -> raw INSERT INTO profiles DENIED.

    This is the fail-closed proof: it is the honored `is_system_mode()` escape — not
    a superuser connection and not a permissive policy — that enables bootstrap. With
    the escape off and no actor, the `profiles_insert` WITH CHECK
    (`is_system_mode() OR id = current_user_id()`) is false on both branches.

    The write is raw SQL inside a nested SAVEPOINT so the expected
    `InsufficientPrivilege` does not poison the ORM session for teardown.
    """
    new_id = uuid4()
    stmt = text("INSERT INTO profiles (id) VALUES (:id)")
    with pytest.raises((ProgrammingError, DBAPIError)) as excinfo:
        async with db_session.begin_nested():
            await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
            await db_session.execute(text("SET LOCAL app.user_id = ''"))
            await db_session.execute(stmt, {"id": new_id})

    assert "row-level security" in str(excinfo.value).lower(), (
        f"expected an RLS denial inserting into profiles, got: {excinfo.value}"
    )
