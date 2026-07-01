"""Tests for the ported `likes-you` domain.

The original Hono domain shipped no `*.test.ts`, so these cover the relevance-filter
contract the port must preserve (these are *relevance* filters; RLS access is
covered by tests/test_rls.py):
  * fetch_likes_you_pool — profiles whose `approved` decision targets the viewer,
    still available: same preference filters, not yet matched, not yet
    decided-by-viewer.
  * the match exclusion (the graph's matched liker is hidden) — the key denial.
  * the decided-by-viewer exclusion.
  * fetch_likes_you_count — count of the same pool.
  * row_to_likes_you_profile — snake->camel incl. the optional pending suggestion.

Reads run against the seeded `graph` under the system-mode `db_session`.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.discover.queries import fetch_likes_you_count, fetch_likes_you_pool
from app.domain.likes_you.transformers import row_to_likes_you_profile
from tests.fixtures.graph import DomainGraph

# `asyncio_mode = "auto"` runs `async def test_*` without a marker.


async def _normalize_ages(graph: DomainGraph, db_session: AsyncSession) -> None:
    """Pin liker DOBs (~30) and widen dater_a's preferred range to [18, 99].

    Likes-you applies the viewer's preference filters to inbound likers; the
    `graph` fixture's faker-advanced ages are order-dependent, so pin them to keep
    membership deterministic.
    """
    in_range = date(1995, 1, 1)
    graph.dater_b.date_of_birth = in_range
    graph.dater_c.date_of_birth = in_range
    graph.dating_profile_a.age_from = 18
    graph.dating_profile_a.age_to = 99
    await db_session.flush()


async def test_likes_you_excludes_already_matched(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # The only inbound `approved` like in the graph is dater_b -> dater_a, but they
    # are already matched, so the pool for dater_a is empty.
    rows = await fetch_likes_you_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    assert graph.dater_b.id not in {r.user_id for r in rows}
    assert await fetch_likes_you_count(db_session, graph.dater_a.id) == 0


async def test_likes_you_returns_unmatched_liker(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_c approves dater_a (no match between them) -> dater_c surfaces.
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    rows = await fetch_likes_you_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}
    assert graph.dater_c.id in user_ids
    assert graph.dater_b.id not in user_ids  # still matched
    assert await fetch_likes_you_count(db_session, graph.dater_a.id) == 1


async def test_likes_you_excludes_decided_by_viewer(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_c likes dater_a, but dater_a has already passed on dater_c -> excluded.
    db_session.add_all(
        [
            Decision(
                actor_id=graph.dater_c.id,
                recipient_id=graph.dater_a.id,
                decision=DecisionType.APPROVED,
            ),
            Decision(
                actor_id=graph.dater_a.id,
                recipient_id=graph.dater_c.id,
                decision=DecisionType.DECLINED,
            ),
        ]
    )
    await db_session.flush()

    rows = await fetch_likes_you_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    assert graph.dater_c.id not in {r.user_id for r in rows}
    assert await fetch_likes_you_count(db_session, graph.dater_a.id) == 0


async def test_likes_you_row_maps_to_camel_case(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    rows = await fetch_likes_you_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    dto = row_to_likes_you_profile(rows[0])

    assert dto.userId == graph.dater_c.id
    assert dto.chosenName == graph.dater_c.chosen_name
    assert dto.profileId == graph.dating_profile_c.id
    # No pending winger suggestion for (dater_a -> dater_c) -> suggestion fields null.
    assert dto.suggestedBy is None
    assert dto.suggesterName is None
    assert dto.wingNote is None
