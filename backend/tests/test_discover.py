from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.enums import City, DatingStatus
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.discover.queries import fetch_discover_pool
from app.domain.discover.transformers import row_to_discover_profile
from app.domain.profiles.enums import Gender
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


async def _normalize_ages(graph: DomainGraph, db_session: AsyncSession) -> None:
    """Pin candidate DOBs (~30) and widen dater_a's preferred range to [18, 99].

    Makes age-filter membership deterministic regardless of the faker-advanced
    seed ages, so a test asserting on dater_b/dater_c isn't order-dependent.
    """
    in_range = date(1995, 1, 1)
    graph.dater_b.date_of_birth = in_range
    graph.dater_c.date_of_birth = in_range
    graph.dating_profile_a.age_from = 18
    graph.dating_profile_a.age_to = 99
    await db_session.flush()


async def test_discover_pool_returns_preference_matches(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_discover_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}

    # dater_b and dater_c match dater_a's prefs (Boston, open, female, in range).
    assert graph.dater_b.id in user_ids
    assert graph.dater_c.id in user_ids
    # Never include self.
    assert graph.dater_a.id not in user_ids


async def test_discover_pool_excludes_out_of_age_range(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Pin a too-young dater_c (16) against dater_a's [24, 38] floor.
    graph.dater_b.date_of_birth = date(1995, 1, 1)  # ~30, in range
    graph.dater_c.date_of_birth = date(2010, 1, 1)  # ~16, below ageFrom
    graph.dating_profile_a.age_from = 24
    graph.dating_profile_a.age_to = 38
    await db_session.flush()

    rows = await fetch_discover_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}
    assert graph.dater_b.id in user_ids
    assert graph.dater_c.id not in user_ids


async def test_discover_pool_orders_suggestions_first(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_discover_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    # The graph seeds a pending winger suggestion (dater_a -> dater_b). It must sort
    # ahead of the un-suggested dater_c.
    first = rows[0]
    assert first.user_id == graph.dater_b.id
    assert first.suggested_by == graph.winger.id
    assert first.suggester_name == graph.winger.chosen_name
    assert first.wing_note == graph.suggestion.note


async def test_discover_row_maps_to_camel_case(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_discover_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    suggested = next(r for r in rows if r.user_id == graph.dater_b.id)
    dto = await row_to_discover_profile(suggested, local_media())

    assert dto.profileId == graph.dating_profile_b.id
    assert dto.userId == graph.dater_b.id
    assert dto.chosenName == graph.dater_b.chosen_name
    assert dto.city == City.BOSTON
    assert dto.datingStatus == DatingStatus.OPEN
    # gender serializes by .value through msgspec -> the Zod enum wire form.
    assert dto.gender is Gender.FEMALE
    assert dto.suggestedBy == graph.winger.id
    assert dto.suggesterName == graph.winger.chosen_name
    assert dto.wingNote == graph.suggestion.note


async def test_discover_pool_excludes_already_decided(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_a passes on dater_c (a NOT-NULL decision) -> dater_c drops out.
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            decision=DecisionType.DECLINED,
        )
    )
    await db_session.flush()

    rows = await fetch_discover_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}
    assert graph.dater_c.id not in user_ids
    # dater_b (only a NULL suggestion against it, not a real decision) stays.
    assert graph.dater_b.id in user_ids


async def test_discover_winger_only_keeps_suggested(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_discover_pool(
        db_session,
        viewer_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
        winger_only=True,
    )
    # Only the pending-suggestion card (dater_b) survives the wingerOnly EXISTS.
    assert {r.user_id for r in rows} == {graph.dater_b.id}


async def test_discover_likes_you_only_excludes_matched(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_b approved dater_a in the graph, but dater_a<->dater_b are already
    # matched -> likesYouOnly excludes them. dater_c approves dater_a fresh (no
    # match) -> dater_c surfaces.
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    rows = await fetch_discover_pool(
        db_session,
        viewer_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
        likes_you_only=True,
    )
    user_ids = {r.user_id for r in rows}
    assert graph.dater_c.id in user_ids
    assert graph.dater_b.id not in user_ids  # already matched
