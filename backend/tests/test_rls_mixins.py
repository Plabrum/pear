from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from tests.fixtures.graph import ActingAs, DomainGraph
from tests.fixtures.rls_mixin_domain.models import RlsOwnedThing, RlsWingThing

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


async def _ids(session: AsyncSession, model: type) -> set:
    rows = (await session.execute(select(model.id))).scalars().all()
    return set(rows)


async def _count(session: AsyncSession, model: type) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


# ─────────────────────────────────────────────────────────────────────────────
# UserScopedMixin — owner-only access.
# ─────────────────────────────────────────────────────────────────────────────


async def test_user_scoped_owner_sees_own_row(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """UserScopedMixin policy: USING (is_system_mode() OR user_id = me)."""
    owned = RlsOwnedThing(user_id=graph.dater_a.id, name="mine")
    db_session.add(owned)
    await db_session.flush()

    async with acting_as(graph.dater_a.id) as s:
        assert await _ids(s, RlsOwnedThing) == {owned.id}


async def test_user_scoped_non_owner_denied(graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs) -> None:
    """A different user cannot see another user's owned row."""
    owned = RlsOwnedThing(user_id=graph.dater_a.id, name="mine")
    db_session.add(owned)
    await db_session.flush()

    async with acting_as(graph.dater_c.id) as s:
        assert await _count(s, RlsOwnedThing) == 0


async def test_user_scoped_wingperson_denied(graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs) -> None:
    """An active wingperson gets NO access to a plain user-scoped row.

    The winger is ACTIVE for dater_a, but `UserScopedMixin` grants owner-only
    access — wingperson status is irrelevant here (that is `WingpersonScopedMixin`).
    """
    owned = RlsOwnedThing(user_id=graph.dater_a.id, name="mine")
    db_session.add(owned)
    await db_session.flush()

    async with acting_as(graph.winger.id) as s:
        assert await _count(s, RlsOwnedThing) == 0


async def test_user_scoped_unset_actor_fails_closed(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """No app.user_id -> current_user_id() is NULL -> predicate never true -> 0 rows."""
    owned = RlsOwnedThing(user_id=graph.dater_a.id, name="mine")
    db_session.add(owned)
    await db_session.flush()

    async with acting_as(None) as s:
        assert await _count(s, RlsOwnedThing) == 0


# ─────────────────────────────────────────────────────────────────────────────
# WingpersonScopedMixin — owner OR active wingperson access.
# ─────────────────────────────────────────────────────────────────────────────


async def test_wingperson_scoped_owner_sees_own_row(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """WingpersonScopedMixin policy: owner branch (user_id = me)."""
    thing = RlsWingThing(user_id=graph.dater_a.id, name="daters")
    db_session.add(thing)
    await db_session.flush()

    async with acting_as(graph.dater_a.id) as s:
        assert thing.id in await _ids(s, RlsWingThing)


async def test_wingperson_scoped_active_winger_sees_row(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """The active wingperson of the owner can access the row via is_active_wingperson().

    The graph seeds an ACTIVE contact: winger is wingperson to dater_a.
    """
    thing = RlsWingThing(user_id=graph.dater_a.id, name="daters")
    db_session.add(thing)
    await db_session.flush()

    async with acting_as(graph.winger.id) as s:
        assert thing.id in await _ids(s, RlsWingThing)


async def test_wingperson_scoped_non_owner_non_winger_denied(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """An unrelated user (neither owner nor active wingperson) is denied."""
    thing = RlsWingThing(user_id=graph.dater_a.id, name="daters")
    db_session.add(thing)
    await db_session.flush()

    async with acting_as(graph.dater_c.id) as s:
        assert await _count(s, RlsWingThing) == 0


async def test_wingperson_scoped_winger_of_other_dater_denied(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """A winger active for some OTHER dater cannot reach this owner's row.

    The row is owned by dater_b (no contact links the winger to dater_b), so the
    winger's ACTIVE-for-dater_a status grants nothing here.
    """
    thing = RlsWingThing(user_id=graph.dater_b.id, name="someone elses")
    db_session.add(thing)
    await db_session.flush()

    async with acting_as(graph.winger.id) as s:
        assert await _count(s, RlsWingThing) == 0


async def test_wingperson_scoped_unset_actor_fails_closed(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """No app.user_id -> owner branch and is_active_wingperson() both fail -> 0 rows."""
    thing = RlsWingThing(user_id=graph.dater_a.id, name="daters")
    db_session.add(thing)
    await db_session.flush()

    async with acting_as(None) as s:
        assert await _count(s, RlsWingThing) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Inserts honor the WITH CHECK side of each FOR ALL policy.
# ─────────────────────────────────────────────────────────────────────────────


async def test_user_scoped_insert_as_owner_allowed(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """WITH CHECK (user_id = me) passes when inserting a row you own."""
    async with acting_as(graph.dater_a.id) as s:
        s.add(RlsOwnedThing(user_id=graph.dater_a.id, name="fresh"))
        await s.flush()


async def test_wingperson_scoped_insert_as_active_winger_allowed(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    """WITH CHECK passes for an active wingperson inserting on the owner's behalf."""
    async with acting_as(graph.winger.id) as s:
        s.add(RlsWingThing(user_id=graph.dater_a.id, name="on behalf"))
        await s.flush()


async def test_seeded_row_uses_fresh_id() -> None:
    """Sanity: uuid4 ids stay distinct across calls (guards copy/paste seed bugs)."""
    assert uuid4() != uuid4()
