from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.enums import City, Interest
from app.domain.decisions.actions import (
    ActOnSuggestion,
    CreateSuggestion,
    RecordDirectDecision,
)
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.exceptions import (
    CannotDecideOnSelfError,
    CannotSuggestSelfError,
    NoPendingSuggestionError,
    NotActiveWingpersonError,
)
from app.domain.decisions.models import Decision
from app.domain.decisions.queries import (
    fetch_pending_suggestions,
    find_mutual_match,
    is_active_wingperson,
)
from app.domain.decisions.schemas import (
    ActSuggestionData,
    DirectDecisionData,
    SuggestData,
)
from app.domain.decisions.transformers import row_to_pending_suggestion
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
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor.

    `push` is an AsyncMock so the (stub) match/suggestion pushes can be asserted.
    """
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
    """The mocked `push.send` coroutine — typed so mock assertions type-check."""
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


# ── decisions actions: happy path ────────────────────────────────────────────


async def test_record_direct_decision_no_match(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a likes dater_c. dater_c has not approved back -> no match.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = DirectDecisionData(recipientId=graph.dater_c.id, decision=DecisionType.APPROVED)

    result = await RecordDirectDecision.execute(data, db_session, deps)
    assert result.created_id is None
    assert await find_mutual_match(db_session, graph.dater_a.id, graph.dater_c.id) is None

    # The decision row was upserted.
    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert row.decision == DecisionType.APPROVED
    _push(deps).assert_not_called()


async def test_record_direct_decision_creates_match_on_mutual(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed dater_c -> dater_a as an existing approval, then dater_a approves dater_c
    # back: the second approval drives match formation (legacy create_match_if_mutual).
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = DirectDecisionData(recipientId=graph.dater_c.id, decision=DecisionType.APPROVED)
    result = await RecordDirectDecision.execute(data, db_session, deps)

    # A match was created (created_id surfaced; ids ordered to satisfy the CHECK).
    assert result.created_id is not None
    match = await find_mutual_match(db_session, graph.dater_a.id, graph.dater_c.id)
    assert match is not None
    assert match.id == result.created_id
    lo, hi = sorted([graph.dater_a.id, graph.dater_c.id], key=str)
    assert match.user_a_id == lo and match.user_b_id == hi
    # Match push fired to both participants (both have a push_token? graph seeds
    # none, so push_tokens_for returns [] — assert it at least didn't error and
    # the match exists). When tokens exist the fan-out is exercised below.
    # (No push tokens in the graph -> send not called.)
    _push(deps).assert_not_called()


async def test_record_direct_decision_match_fires_push_when_tokens(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    # Give both daters push tokens so the match fan-out is exercised.
    graph.dater_a.push_token = "ExpoTokenA"
    graph.dater_c.push_token = "ExpoTokenC"
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = DirectDecisionData(recipientId=graph.dater_c.id, decision=DecisionType.APPROVED)
    await RecordDirectDecision.execute(data, db_session, deps)

    assert _push(deps).await_count == 2
    # push.send(token, title, body) — title is the second positional arg.
    titles = {call.args[1] for call in _push(deps).await_args_list}
    assert titles == {"It's a Match! 🎉"}
    tokens = {call.args[0] for call in _push(deps).await_args_list}
    assert tokens == {"ExpoTokenA", "ExpoTokenC"}


async def test_record_direct_decision_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = DirectDecisionData(recipientId=graph.dater_a.id, decision=DecisionType.APPROVED)
    with pytest.raises(CannotDecideOnSelfError):
        await RecordDirectDecision.execute(data, db_session, deps)


async def test_act_on_suggestion_happy(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a acts (approve) on the winger's pending suggestion of dater_b.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = ActSuggestionData(recipientId=graph.dater_b.id, decision=DecisionType.APPROVED)

    result = await ActOnSuggestion.execute(data, db_session, deps)
    assert result.message  # recorded

    # The pending suggestion is now finalised to 'approved'.
    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_b.id,
            )
        )
    ).scalar_one()
    assert row.decision == DecisionType.APPROVED
    # dater_b -> dater_a was already approved in the graph, so acting approve here
    # makes it mutual -> a match is formed.
    match = await find_mutual_match(db_session, graph.dater_a.id, graph.dater_b.id)
    assert match is not None
    assert result.created_id == match.id


async def test_act_on_suggestion_none_pending_404(graph: DomainGraph, db_session: AsyncSession) -> None:
    # No pending suggestion from dater_a to dater_c -> 404.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = ActSuggestionData(recipientId=graph.dater_c.id, decision=DecisionType.APPROVED)
    with pytest.raises(NoPendingSuggestionError):
        await ActOnSuggestion.execute(data, db_session, deps)


async def test_create_suggestion_happy(graph: DomainGraph, db_session: AsyncSession) -> None:
    # winger (active for dater_a) suggests dater_c to dater_a, with a note.
    graph.dater_a.push_token = "ExpoTokenA"
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = SuggestData(daterId=graph.dater_a.id, recipientId=graph.dater_c.id, note="You two!")

    assert await is_active_wingperson(db_session, graph.dater_a.id, graph.winger.id) is True
    result = await CreateSuggestion.execute(data, db_session, deps)
    assert result.message == "Suggestion created"

    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert row.suggested_by == graph.winger.id
    assert row.decision is None  # pending — the dater must act
    assert row.note == "You two!"
    # A new pending suggestion -> the dater gets a push.
    _push(deps).assert_awaited_once()
    call = _push(deps).await_args
    assert call is not None
    assert call.args[0] == "ExpoTokenA"


async def test_create_suggestion_gate_denied_not_wingperson(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is NOT a wingperson for dater_a -> 403, no row written.
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.WINGER)
    data = SuggestData(daterId=graph.dater_a.id, recipientId=graph.dater_b.id)
    with pytest.raises(NotActiveWingpersonError):
        await CreateSuggestion.execute(data, db_session, deps)


async def test_create_suggestion_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = SuggestData(daterId=graph.dater_a.id, recipientId=graph.dater_a.id)
    with pytest.raises(CannotSuggestSelfError):
        await CreateSuggestion.execute(data, db_session, deps)


async def test_create_suggestion_declined_no_push(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A 'declined' suggestion bypasses the dater's feed -> no push.
    graph.dater_a.push_token = "ExpoTokenA"
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = SuggestData(
        daterId=graph.dater_a.id,
        recipientId=graph.dater_c.id,
        decision=DecisionType.DECLINED,
    )
    await CreateSuggestion.execute(data, db_session, deps)
    _push(deps).assert_not_called()


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
    # firstPhoto is now a presigned GET URL wrapping the stored key.
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
