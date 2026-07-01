from __future__ import annotations

from datetime import date
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.enums import City
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.discover.queries import fetch_wing_pool, is_active_wingperson
from app.domain.wing_pool.transformers import row_to_wing_profile
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` runs `async def test_*` without a marker.


async def _normalize_ages(graph: DomainGraph, db_session: AsyncSession) -> None:
    """Pin candidate DOBs (~30) and widen dater_a's preferred range to [18, 99].

    The wing-pool scopes by the DATER's prefs; the `graph` fixture's faker-advanced
    ages are order-dependent, so pin them to keep membership deterministic.
    """
    in_range = date(1995, 1, 1)
    graph.dater_b.date_of_birth = in_range
    graph.dater_c.date_of_birth = in_range
    graph.dating_profile_a.age_from = 18
    graph.dating_profile_a.age_to = 99
    await db_session.flush()


# ── The 403 gate ─────────────────────────────────────────────────────────────


async def test_is_active_wingperson_true_for_active_contact(graph: DomainGraph, db_session: AsyncSession) -> None:
    assert await is_active_wingperson(db_session, graph.winger.id, graph.dater_a.id) is True


async def test_is_active_wingperson_false_for_unrelated_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c has no contact with the winger -> the route would raise 403.
    assert await is_active_wingperson(db_session, graph.winger.id, graph.dater_c.id) is False
    # A random non-winger is likewise denied.
    assert await is_active_wingperson(db_session, uuid4(), graph.dater_a.id) is False


# ── The pool ─────────────────────────────────────────────────────────────────


async def test_wing_pool_returns_dater_scoped_candidates(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_wing_pool(
        db_session,
        winger_id=graph.winger.id,
        dater_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
    )
    user_ids = {r.user_id for r in rows}

    # Candidates matching dater_a's prefs, minus the dater and the winger.
    assert graph.dater_b.id in user_ids
    assert graph.dater_c.id in user_ids
    assert graph.dater_a.id not in user_ids
    assert graph.winger.id not in user_ids


async def test_wing_pool_excludes_daters_decided_candidates(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_a has already passed on dater_c -> the winger won't see dater_c.
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            decision=DecisionType.DECLINED,
        )
    )
    await db_session.flush()

    rows = await fetch_wing_pool(
        db_session,
        winger_id=graph.winger.id,
        dater_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
    )
    assert graph.dater_c.id not in {r.user_id for r in rows}


async def test_wing_profile_maps_to_camel_case(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_wing_pool(
        db_session,
        winger_id=graph.winger.id,
        dater_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
    )
    row = next(r for r in rows if r.user_id == graph.dater_b.id)
    dto = await row_to_wing_profile(row, local_media())

    assert dto.profileId == graph.dating_profile_b.id
    assert dto.userId == graph.dater_b.id
    assert dto.chosenName == graph.dater_b.chosen_name
    assert dto.city == City.BOSTON
    # WingProfile carries a single firstPhoto (str | None), not a photos array.
    assert hasattr(dto, "firstPhoto")
    assert not hasattr(dto, "photos")
