from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.domain.dating_profiles.actions import Like
from app.domain.dating_profiles.enums import City, Interest
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.decisions.queries import (
    fetch_my_suggestions,
    fetch_pending_suggestions,
    find_mutual_match,
)
from app.domain.decisions.tasks import form_match
from app.domain.decisions.transformers import (
    SuggestionRow,
    row_to_pending_suggestion,
    transform_my_suggestion,
)
from app.domain.matches.models import Match
from app.domain.matches.queries import (
    fetch_match_other_user_id,
    fetch_matches,
    fetch_prompts_for_user,
    fetch_wing_note_for_match,
)
from app.domain.matches.transformers import (
    MatchPromptRow,
    MatchRow,
    WingNoteRow,
    build_match_sheet,
    row_to_match,
    row_to_match_prompt,
    row_to_wing_note,
)
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor."""
    push = MagicMock()
    push.send = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


def _push(deps: ActionDeps) -> AsyncMock:
    return cast(AsyncMock, deps.push.send)


# ── decisions: reads ─────────────────────────────────────────────────────────


async def test_fetch_pending_suggestions(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_pending_suggestions(db_session, graph.dater_a.id)
    # The graph seeds exactly one winger-suggested pending card for dater_a.
    assert len(rows) == 1
    sid, recipient_id, note, created_at, winger_id, winger_name = rows[0]
    assert recipient_id == graph.dater_b.id
    assert winger_id == graph.winger.id
    assert winger_name == graph.winger.chosen_name

    dto = row_to_pending_suggestion(
        suggestion_id=sid,
        recipient_id=recipient_id,
        note=note,
        created_at=created_at,
        winger_id=winger_id,
        winger_name=winger_name,
    )
    assert dto.recipientId == graph.dater_b.id
    assert dto.wingerName == graph.winger.chosen_name


async def test_fetch_my_suggestions(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger authored exactly one suggestion (dater_a -> dater_b, pending).
    rows = await fetch_my_suggestions(db_session, graph.winger.id, limit=50)
    assert len(rows) == 1
    row = rows[0]
    assert row.dater_id == graph.dater_a.id
    assert row.dater_name == graph.dater_a.chosen_name
    assert row.recipient_name == graph.dater_b.chosen_name

    dto = transform_my_suggestion(row)
    assert dto.id.startswith("suggestion:")
    assert dto.daterId == graph.dater_a.id
    assert dto.suggestedName == graph.dater_b.chosen_name
    # Pending (decision IS NULL) and not yet matched between this pair -> "pending".
    assert dto.status == "pending"


async def test_fetch_my_suggestions_empty_for_non_suggester(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a authored no winger suggestions.
    assert await fetch_my_suggestions(db_session, graph.dater_a.id, limit=50) == []


def test_transform_my_suggestion_matched() -> None:
    row = SuggestionRow(
        id=uuid4(),
        decision=DecisionType.APPROVED,
        has_match=True,
        dater_id=uuid4(),
        dater_name="Alex",
        recipient_name="Sam",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    assert transform_my_suggestion(row).status == "matched"


def test_transform_my_suggestion_not_accepted() -> None:
    row = SuggestionRow(
        id=uuid4(),
        decision=DecisionType.DECLINED,
        has_match=False,
        dater_id=uuid4(),
        dater_name="Alex",
        recipient_name="Sam",
        created_at=None,
    )
    assert transform_my_suggestion(row).status == "not_accepted"


# ── the merged Like flips a winger pending row (decisions side) ───────────────


async def test_merged_like_flips_winger_pending_row(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph's pending winger suggestion (actor=dater_a, recipient=dater_b) is
    # finalised — not duplicated — when dater_a likes dater_b's profile, and the
    # winger's people-activity flips from pending to matched (dater_b already
    # approved dater_a, so a match forms).
    deps = _deps(db_session, user_id=graph.dater_a.id)
    await Like.execute(graph.dating_profile_b, EmptyActionData(), db_session, deps)

    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_b.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].decision == DecisionType.APPROVED
    assert rows[0].suggested_by == graph.winger.id

    # The winger's people-activity for this card now reports "matched".
    my = await fetch_my_suggestions(db_session, graph.winger.id, limit=50)
    card = next(r for r in my if r.recipient_name == graph.dater_b.chosen_name)
    assert transform_my_suggestion(card).status == "matched"
    assert await find_mutual_match(db_session, graph.dater_a.id, graph.dater_b.id) is not None


# ── FORM_MATCH task (match formation moved off the request path) ──────────────


def _ctx() -> dict[str, object]:
    """Sync-dispatch ctx: just the config (no worker-injected push client)."""
    return {"config": config}


async def _count_matches(db_session: AsyncSession, a, b) -> int:
    lo, hi = sorted([a, b], key=str)
    rows = (await db_session.execute(select(Match).where(Match.user_a_id == lo, Match.user_b_id == hi))).scalars().all()
    return len(rows)


async def test_form_match_creates_on_mutual(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a and dater_c mutually approve, with no match yet — the task forms it.
    db_session.add_all(
        [
            Decision(actor_id=graph.dater_a.id, recipient_id=graph.dater_c.id, decision=DecisionType.APPROVED),
            Decision(actor_id=graph.dater_c.id, recipient_id=graph.dater_a.id, decision=DecisionType.APPROVED),
        ]
    )
    await db_session.flush()
    assert await _count_matches(db_session, graph.dater_a.id, graph.dater_c.id) == 0

    await form_match(
        _ctx(),
        transaction=db_session,
        actor_id=str(graph.dater_a.id),
        recipient_id=str(graph.dater_c.id),
    )

    assert await find_mutual_match(db_session, graph.dater_a.id, graph.dater_c.id) is not None
    assert await _count_matches(db_session, graph.dater_a.id, graph.dater_c.id) == 1


async def test_form_match_is_idempotent(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph already seeds the dater_a <-> dater_b match. Re-running the task must
    # not insert a duplicate (it returns early on an existing match).
    assert await _count_matches(db_session, graph.dater_a.id, graph.dater_b.id) == 1
    await form_match(
        _ctx(),
        transaction=db_session,
        actor_id=str(graph.dater_a.id),
        recipient_id=str(graph.dater_b.id),
    )
    assert await _count_matches(db_session, graph.dater_a.id, graph.dater_b.id) == 1


async def test_form_match_noop_when_not_mutual(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Only one side approved -> no match is formed (the second like will re-enqueue).
    db_session.add(Decision(actor_id=graph.dater_a.id, recipient_id=graph.dater_c.id, decision=DecisionType.APPROVED))
    await db_session.flush()

    await form_match(
        _ctx(),
        transaction=db_session,
        actor_id=str(graph.dater_a.id),
        recipient_id=str(graph.dater_c.id),
    )
    assert await find_mutual_match(db_session, graph.dater_a.id, graph.dater_c.id) is None
    assert await _count_matches(db_session, graph.dater_a.id, graph.dater_c.id) == 0


# ── matches: reads ───────────────────────────────────────────────────────────


async def test_fetch_matches(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds one match (dater_a <-> dater_b) with one message.
    rows = await fetch_matches(db_session, graph.dater_a.id)
    assert len(rows) == 1
    row = rows[0]
    assert row.match_id == graph.match.id
    assert row.other_user_id == graph.dater_b.id
    assert row.chosen_name == graph.dater_b.chosen_name
    assert row.has_messages is True
    assert row.city == City.BOSTON

    dto = await row_to_match(row, local_media())
    assert dto.matchId == graph.match.id
    assert dto.other.id == graph.dater_b.id
    assert dto.hasMessages is True


async def test_fetch_matches_empty(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c has no matches.
    assert await fetch_matches(db_session, graph.dater_c.id) == []


async def test_match_sheet_other_user_id_and_note(graph: DomainGraph, db_session: AsyncSession) -> None:
    other_id = await fetch_match_other_user_id(db_session, graph.dater_a.id, graph.match.id)
    assert other_id == graph.dater_b.id

    # The graph's winger-suggested decision (actor=dater_a, recipient=dater_b)
    # carries a note -> the wing note surfaces on the sheet.
    wing_note = await fetch_wing_note_for_match(db_session, graph.dater_a.id, graph.dater_b.id)
    assert wing_note is not None
    assert wing_note.note is not None
    assert wing_note.winger_id == graph.winger.id

    prompts = await fetch_prompts_for_user(db_session, graph.dater_b.id)
    sheet = build_match_sheet(wing_note, prompts)
    assert sheet.wingNote is not None
    assert sheet.wingNote.winger is not None
    assert sheet.wingNote.winger.id == graph.winger.id


async def test_match_sheet_other_user_id_not_participant(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is not party to the match -> None (route raises 404).
    assert await fetch_match_other_user_id(db_session, graph.dater_c.id, graph.match.id) is None


# ── matches transformers ─────────────────────────────────────────────────────


_BASE_MATCH_ROW = MatchRow(
    match_id=UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
    created_at=datetime(2026, 1, 1, tzinfo=UTC),
    has_messages=False,
    other_user_id=UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    chosen_name="Alex",
    date_of_birth=datetime(1995, 6, 15, tzinfo=UTC),
    age=30,
    city=City.NEW_YORK,
    bio="Love hiking",
    interests=[Interest.OUTDOORS, Interest.COOKING],
    first_photo="https://example.com/photo.jpg",
)


async def test_row_to_match_maps_all_fields() -> None:
    result = await row_to_match(_BASE_MATCH_ROW, local_media())
    assert result.matchId == _BASE_MATCH_ROW.match_id
    assert result.hasMessages is False
    assert result.other.id == _BASE_MATCH_ROW.other_user_id
    assert result.other.chosenName == "Alex"
    assert result.other.city == City.NEW_YORK
    assert result.other.interests == [Interest.OUTDOORS, Interest.COOKING]
    assert result.other.firstPhoto is not None
    assert _BASE_MATCH_ROW.first_photo is not None
    assert _BASE_MATCH_ROW.first_photo in result.other.firstPhoto


async def test_row_to_match_empty_array_when_interests_none() -> None:
    row = MatchRow(**{**_BASE_MATCH_ROW.__dict__, "interests": None})
    assert (await row_to_match(row, local_media())).other.interests == []


def test_row_to_wing_note_none_when_row_none() -> None:
    assert row_to_wing_note(None) is None


def test_row_to_wing_note_none_when_note_none() -> None:
    row = WingNoteRow(note=None, suggested_by=uuid4(), winger_id=None, winger_chosen_name=None)
    assert row_to_wing_note(row) is None


def test_row_to_wing_note_maps_note_and_winger() -> None:
    wid = uuid4()
    row = WingNoteRow(note="Great match!", suggested_by=wid, winger_id=wid, winger_chosen_name="Sam")
    result = row_to_wing_note(row)
    assert result is not None
    assert result.note == "Great match!"
    assert result.suggestedBy == wid
    assert result.winger is not None and result.winger.chosenName == "Sam"


def test_row_to_wing_note_winger_none_when_winger_id_none() -> None:
    row = WingNoteRow(note="Nice person", suggested_by=None, winger_id=None, winger_chosen_name=None)
    result = row_to_wing_note(row)
    assert result is not None and result.winger is None


def test_row_to_match_prompt_with_template() -> None:
    tid = uuid4()
    row = MatchPromptRow(
        id=uuid4(),
        answer="I love sunsets",
        template_id=tid,
        template_question="What is your favourite time of day?",
    )
    result = row_to_match_prompt(row)
    assert result.answer == "I love sunsets"
    assert result.template is not None
    assert result.template.id == tid
    assert result.template.question == "What is your favourite time of day?"


def test_row_to_match_prompt_template_none() -> None:
    row = MatchPromptRow(id=uuid4(), answer="No template", template_id=None, template_question=None)
    assert row_to_match_prompt(row).template is None


def test_build_match_sheet_assembles() -> None:
    wid = uuid4()
    wing_note = WingNoteRow(note="They are great", suggested_by=wid, winger_id=wid, winger_chosen_name="Sam")
    prompts = [MatchPromptRow(id=uuid4(), answer="Answer A", template_id=uuid4(), template_question="Question?")]
    result = build_match_sheet(wing_note, prompts)
    assert result.wingNote is not None and result.wingNote.note == "They are great"
    assert len(result.prompts) == 1
    assert result.prompts[0].answer == "Answer A"


def test_build_match_sheet_null_wing_note() -> None:
    result = build_match_sheet(None, [])
    assert result.wingNote is None
    assert result.prompts == []
