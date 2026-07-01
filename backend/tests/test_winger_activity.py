from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.winger_activity.queries import (
    PhotoRow,
    PromptRow,
    SuggestionRow,
    fetch_people_activity,
    fetch_photos_activity,
    fetch_prompts_activity,
)
from app.domain.winger_activity.transformers import (
    transform_photo,
    transform_prompt,
    transform_suggestion,
)
from app.domain.winger_tabs.queries import WingerTabRow, fetch_winger_tabs
from app.domain.winger_tabs.transformers import rows_to_winger_tabs
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# Deterministic fake-URL media client — `storage_url` keys resolve to presigned
# GET URLs (no AWS). Used by the transform_photo cases.
_media = local_media()

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


# ── winger-activity: people feed (reads) ─────────────────────────────────────


async def test_fetch_people_activity_pending(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds exactly one winger-suggested card (dater_a -> dater_b),
    # decision IS NULL -> status "pending".
    rows = await fetch_people_activity(db_session, graph.winger.id, 50)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == graph.suggestion.id
    assert row.dater_id == graph.dater_a.id
    assert row.dater_name == graph.dater_a.chosen_name
    assert row.recipient_name == graph.dater_b.chosen_name
    assert row.decision is None
    # No match joins dater_a <-> dater_b in the *suggestion direction*? The graph
    # DOES seed a match between dater_a and dater_b, so has_match is True — but the
    # status is still "pending" because the suggestion's decision is NULL.
    assert row.has_match is True

    dto = transform_suggestion(row)
    assert dto.id == f"suggestion:{graph.suggestion.id}"
    assert dto.daterId == graph.dater_a.id
    assert dto.suggestedName == graph.dater_b.chosen_name
    assert dto.status == "pending"


async def test_fetch_people_activity_matched(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Approve the winger's suggestion AND ensure a match exists (the graph already
    # seeds the dater_a<->dater_b match) -> status "matched".
    graph.suggestion.decision = DecisionType.APPROVED
    await db_session.flush()

    rows = await fetch_people_activity(db_session, graph.winger.id, 50)
    row = next(r for r in rows if r.id == graph.suggestion.id)
    assert row.decision is DecisionType.APPROVED
    assert row.has_match is True
    assert transform_suggestion(row).status == "matched"


async def test_fetch_people_activity_not_accepted(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A declined winger suggestion -> status "not_accepted", regardless of match.
    declined = Decision(
        actor_id=graph.dater_a.id,
        recipient_id=graph.dater_c.id,
        decision=DecisionType.DECLINED,
        suggested_by=graph.winger.id,
    )
    db_session.add(declined)
    await db_session.flush()

    rows = await fetch_people_activity(db_session, graph.winger.id, 50)
    row = next(r for r in rows if r.id == declined.id)
    assert transform_suggestion(row).status == "not_accepted"


async def test_fetch_people_activity_scoped_to_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a's own (non-suggested) approval of dater_b must NOT surface in the
    # winger's people feed — only suggested_by = winger rows do.
    rows = await fetch_people_activity(db_session, graph.winger.id, 50)
    assert all(r.id != graph.decision.id for r in rows)
    # A winger with no suggestions sees nothing.
    assert await fetch_people_activity(db_session, graph.dater_c.id, 50) == []


async def test_people_activity_honors_limit(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed a second suggestion so the feed has > 1 row, then assert limit=1 trims it.
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            decision=None,
            suggested_by=graph.winger.id,
        )
    )
    await db_session.flush()
    assert len(await fetch_people_activity(db_session, graph.winger.id, 50)) == 2
    assert len(await fetch_people_activity(db_session, graph.winger.id, 1)) == 1


# ── winger-activity: photos feed (reads) ─────────────────────────────────────


async def test_fetch_photos_activity(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds one winger-suggested pending photo for dater_a.
    rows = await fetch_photos_activity(db_session, graph.winger.id, 50)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == graph.pending_photo.id
    assert row.dater_id == graph.dater_a.id
    assert row.dater_name == graph.dater_a.chosen_name
    assert row.approved_at is None
    assert row.rejected_at is None

    dto = await transform_photo(row, _media)
    assert dto.daterId == graph.dater_a.id
    # storageUrl is a presigned GET URL wrapping the media's servable key. The
    # pending photo's media is READY, so its processed (WebP) key is servable.
    assert dto.storageUrl.startswith("http")
    assert graph.pending_media.processed_key in dto.storageUrl
    assert dto.status == "pending"


async def test_fetch_photos_activity_scoped_to_suggester(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The approved photo was self-uploaded (suggester_id is None), so it must NOT
    # appear in the winger's photo feed.
    rows = await fetch_photos_activity(db_session, graph.winger.id, 50)
    assert all(r.id != graph.approved_photo.id for r in rows)
    assert await fetch_photos_activity(db_session, graph.dater_c.id, 50) == []


# ── winger-activity: prompts feed (reads) ────────────────────────────────────


async def test_fetch_prompts_activity(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds one winger-authored prompt response, pending approval.
    rows = await fetch_prompts_activity(db_session, graph.winger.id, 50)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == graph.prompt_response.id
    assert row.dater_id == graph.dater_a.id
    assert row.dater_name == graph.dater_a.chosen_name
    assert row.message == graph.prompt_response.message
    assert row.is_approved is False
    assert row.is_rejected is False

    dto = transform_prompt(row)
    assert dto.daterId == graph.dater_a.id
    assert dto.promptQuestion  # joined from the template
    assert dto.status == "pending"


async def test_fetch_prompts_activity_scoped_to_author(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A winger with no authored responses sees nothing.
    assert await fetch_prompts_activity(db_session, graph.dater_c.id, 50) == []


# ── winger-tabs (reads) ──────────────────────────────────────────────────────


async def test_fetch_winger_tabs(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a has one pending winger-suggested card (decision IS NULL) -> the
    # suggesting winger appears as one tab.
    rows = await fetch_winger_tabs(db_session, graph.dater_a.id)
    assert len(rows) == 1
    assert rows[0].id == graph.winger.id
    assert rows[0].chosen_name == graph.winger.chosen_name

    tabs = rows_to_winger_tabs(rows)
    assert len(tabs) == 1
    assert tabs[0].id == graph.winger.id
    assert tabs[0].name == graph.winger.chosen_name


async def test_fetch_winger_tabs_dedupes(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A second pending suggestion from the SAME winger must collapse to one tab.
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            decision=None,
            suggested_by=graph.winger.id,
        )
    )
    await db_session.flush()
    rows = await fetch_winger_tabs(db_session, graph.dater_a.id)
    assert len(rows) == 2  # two pending suggestion rows...
    assert len(rows_to_winger_tabs(rows)) == 1  # ...one distinct winger.


async def test_fetch_winger_tabs_excludes_acted(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Once the dater acts on the suggestion (decision no longer NULL), the winger
    # drops out of the tabs.
    graph.suggestion.decision = DecisionType.APPROVED
    await db_session.flush()
    assert await fetch_winger_tabs(db_session, graph.dater_a.id) == []


async def test_fetch_winger_tabs_empty_for_unrelated(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c has no pending winger suggestions.
    assert await fetch_winger_tabs(db_session, graph.dater_c.id) == []
    assert rows_to_winger_tabs([]) == []


# ── transformers: pure status-folding unit tests ─────────────────────────────


def _suggestion(decision: DecisionType | None, has_match: bool) -> SuggestionRow:
    return SuggestionRow(
        id=uuid4(),
        decision=decision,
        has_match=has_match,
        dater_id=uuid4(),
        dater_name="Dana",
        recipient_name="Rory",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_transform_suggestion_status_matrix() -> None:
    assert transform_suggestion(_suggestion(DecisionType.DECLINED, True)).status == "not_accepted"
    assert transform_suggestion(_suggestion(DecisionType.DECLINED, False)).status == "not_accepted"
    assert transform_suggestion(_suggestion(DecisionType.APPROVED, True)).status == "matched"
    # approved but no match yet -> still pending
    assert transform_suggestion(_suggestion(DecisionType.APPROVED, False)).status == "pending"
    assert transform_suggestion(_suggestion(None, False)).status == "pending"
    assert transform_suggestion(_suggestion(None, True)).status == "pending"


def test_transform_suggestion_id_prefix_and_iso() -> None:
    row = _suggestion(None, False)
    dto = transform_suggestion(row)
    assert dto.id == f"suggestion:{row.id}"
    assert dto.createdAt == "2026-01-01T00:00:00+00:00"


def _photo(approved: datetime | None, rejected: datetime | None) -> PhotoRow:
    return PhotoRow(
        id=uuid4(),
        dater_id=uuid4(),
        dater_name="Dana",
        storage_url="https://example.com/p.jpg",
        approved_at=approved,
        rejected_at=rejected,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


async def test_transform_photo_status_matrix() -> None:
    now = datetime(2026, 1, 2, tzinfo=UTC)
    # rejected wins over approved
    assert (await transform_photo(_photo(now, now), _media)).status == "not_accepted"
    assert (await transform_photo(_photo(None, now), _media)).status == "not_accepted"
    assert (await transform_photo(_photo(now, None), _media)).status == "approved"
    assert (await transform_photo(_photo(None, None), _media)).status == "pending"


def _prompt(is_approved: bool, is_rejected: bool) -> PromptRow:
    return PromptRow(
        id=uuid4(),
        dater_id=uuid4(),
        dater_name="Dana",
        prompt_question="Q?",
        message="hi",
        is_approved=is_approved,
        is_rejected=is_rejected,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_transform_prompt_status_matrix() -> None:
    # rejected wins over approved
    assert transform_prompt(_prompt(True, True)).status == "not_accepted"
    assert transform_prompt(_prompt(False, True)).status == "not_accepted"
    assert transform_prompt(_prompt(True, False)).status == "accepted"
    assert transform_prompt(_prompt(False, False)).status == "pending"


def test_rows_to_winger_tabs_preserves_first_seen_order() -> None:
    w1, w2 = uuid4(), uuid4()
    rows = [
        WingerTabRow(id=w1, chosen_name="Wanda", created_at=datetime(2026, 1, 3, tzinfo=UTC)),
        WingerTabRow(id=w2, chosen_name="Walt", created_at=datetime(2026, 1, 2, tzinfo=UTC)),
        WingerTabRow(id=w1, chosen_name="Wanda", created_at=datetime(2026, 1, 1, tzinfo=UTC)),
    ]
    tabs = rows_to_winger_tabs(rows)
    assert [t.id for t in tabs] == [w1, w2]
    assert [t.name for t in tabs] == ["Wanda", "Walt"]
