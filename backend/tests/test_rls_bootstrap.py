from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TestConfig
from app.domain.profiles.models import Profile
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity
from app.platform.auth.service import AuthService
from tests.fixtures.ids import fake_id

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


async def test_first_login_bootstrap_succeeds_without_actor_or_system_mode(
    db_session: AsyncSession, test_config: TestConfig
) -> None:
    """As `pear_app`, NO system mode + NO actor -> AuthService bootstraps a profile.

    Mirrors the unauthenticated login route: there is no `app.user_id` yet and system
    mode is OFF. The `profiles` identity table carries no RLS, so
    `AuthService.find_or_create_identity` just inserts the new profile + identity rows.
    We first clear any fixture GUCs so it is unambiguously an open-table insert — not a
    leftover actor setting or system mode — that allows the writes.
    """
    # Start from the true unauthenticated bootstrap condition: escape OFF, no actor.
    await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
    await db_session.execute(text("SET LOCAL app.user_id = ''"))

    before_profiles = (await db_session.execute(select(func.count()).select_from(Profile))).scalar_one()
    before_identities = (await db_session.execute(select(func.count()).select_from(AuthIdentity))).scalar_one()

    service = AuthService(db_session, test_config)
    subject = f"bootstrap-{fake_id()}@example.com"

    profile, created = await service.find_or_create_identity(AuthProvider.EMAIL, subject)

    assert created is True
    assert profile.id is not None

    # The bootstrap did NOT need to scope an actor or flip system mode: both GUCs are
    # still in their unauthenticated state.
    actor = (await db_session.execute(text("SELECT NULLIF(current_setting('app.user_id', true), '')"))).scalar_one()
    assert actor is None
    system_mode = (
        await db_session.execute(
            text("SELECT coalesce(nullif(current_setting('app.is_system_mode', true), '')::boolean, false)")
        )
    ).scalar_one()
    assert system_mode is False

    # The profile + identity rows are genuinely persisted (visible in this tx).
    after_profiles = (await db_session.execute(select(func.count()).select_from(Profile))).scalar_one()
    after_identities = (await db_session.execute(select(func.count()).select_from(AuthIdentity))).scalar_one()
    assert after_profiles == before_profiles + 1
    assert after_identities == before_identities + 1

    identity = (
        await db_session.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.EMAIL,
                AuthIdentity.provider_subject == subject,
            )
        )
    ).scalar_one()
    assert identity.profile_id == profile.id

    # Idempotent: a second call resolves the SAME profile without creating rows.
    profile2, created2 = await service.find_or_create_identity(AuthProvider.EMAIL, subject)
    assert created2 is False
    assert profile2.id == profile.id


async def test_raw_profile_insert_allowed_without_system_mode_or_actor(db_session: AsyncSession) -> None:
    """As `pear_app`, escape OFF + NO app.user_id -> raw INSERT INTO profiles SUCCEEDS.

    The identity table is deliberately left open (no RLS): a profile row's scope is
    only knowable after its id exists, so the root table relies on the app layer and
    the relationship-scoped child tables for its floor rather than a self-referential
    insert policy. This is the proof that the floor was intentionally removed here —
    the insert that the old policy denied now goes through.
    """
    new_id = fake_id()
    async with db_session.begin_nested():
        await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
        await db_session.execute(text("SET LOCAL app.user_id = ''"))
        await db_session.execute(text("INSERT INTO profiles (id) VALUES (:id)"), {"id": new_id})

    persisted = (
        await db_session.execute(select(func.count()).select_from(Profile).where(Profile.id == new_id))
    ).scalar_one()
    assert persisted == 1
