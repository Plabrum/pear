from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

# Importing the messages domain's actions module registers the MESSAGE_ACTIONS
# group (and its Send/MarkRead actions) on the singleton ActionRegistry at import
# time. The test registry is otherwise only seeded with models (see conftest), so
# without this import `resolve_group(MESSAGE_ACTIONS)` would miss.
import app.domain.messages.actions  # noqa: F401
from app.domain.matches.queries import fetch_match_other_user_id, fetch_matches
from app.domain.matches.transformers import row_to_match
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import resolve_group
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph
from tests.fixtures.ids import fake_id
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.

# The MESSAGE_ACTIONS group surfaces exactly these two object actions on a Match
# (combined keys are `<group_value>__<action_key>`).
SEND_KEY = "message_actions__send"
MARK_READ_KEY = "message_actions__mark_read"


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor (services mocked)."""
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=MagicMock(send=AsyncMock()),
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
        realtime=MagicMock(),
        media=local_media(),
    )


# ── Reads: fetch_matches shape ───────────────────────────────────────────────


async def test_fetch_matches_carries_participants(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a is party to exactly one match (with dater_b).
    rows = await fetch_matches(db_session, graph.dater_a.id)
    assert len(rows) == 1
    row = rows[0]

    assert row.match_id == graph.match.id
    # The other participant is dater_b, with their summary folded in.
    assert row.other_user_id == graph.dater_b.id
    assert row.chosen_name == graph.dater_b.chosen_name
    # Both participant ids carry through (ordered: user_a_id < user_b_id) so the
    # transformer can build the transient Match stub for action gating.
    assert row.user_a_id == graph.match.user_a_id
    assert row.user_b_id == graph.match.user_b_id
    assert {row.user_a_id, row.user_b_id} == {graph.dater_a.id, graph.dater_b.id}
    # graph seeds one message in the match.
    assert row.has_messages is True


async def test_fetch_matches_empty_for_unrelated_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is not party to any match.
    assert await fetch_matches(db_session, graph.dater_c.id) == []


async def test_fetch_match_other_user_id(graph: DomainGraph, db_session: AsyncSession) -> None:
    assert await fetch_match_other_user_id(db_session, graph.dater_a.id, graph.match.id) == graph.dater_b.id
    assert await fetch_match_other_user_id(db_session, graph.dater_b.id, graph.match.id) == graph.dater_a.id
    # A non-party (winger) gets None -> 404.
    assert await fetch_match_other_user_id(db_session, graph.winger.id, graph.match.id) is None
    # A non-existent match id is also None.
    assert await fetch_match_other_user_id(db_session, graph.dater_a.id, fake_id()) is None


# ── Reads: action hydration on MatchSummary ──────────────────────────────────


async def test_row_to_match_hydrates_message_actions_for_party(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_matches(db_session, graph.dater_a.id)
    deps = _deps(db_session, user_id=graph.dater_a.id)
    group = resolve_group(ActionGroupType.MESSAGE_ACTIONS)

    summary = await row_to_match(rows[0], local_media(), group, deps)

    # A viewer who is party to the match sees both message actions: send + mark_read.
    keys = {a.action for a in summary.actions}
    assert keys == {SEND_KEY, MARK_READ_KEY}
    # Every surfaced action is tagged with the MESSAGE_ACTIONS group and available
    # (the gate reads only Match.user_a_id / user_b_id, no disabled reason).
    for action in summary.actions:
        assert action.action_group_type == ActionGroupType.MESSAGE_ACTIONS
        assert action.available is True
        assert action.disabled_reason is None


async def test_row_to_match_no_actions_for_non_party(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Fetch dater_a's match row, but hydrate actions as a NON-party actor (dater_c).
    # The MESSAGE_ACTIONS gate (`_viewer_in_match`) reads only the participant ids,
    # so neither send nor mark_read is offered.
    rows = await fetch_matches(db_session, graph.dater_a.id)
    deps = _deps(db_session, user_id=graph.dater_c.id)
    group = resolve_group(ActionGroupType.MESSAGE_ACTIONS)

    summary = await row_to_match(rows[0], local_media(), group, deps)
    assert summary.actions == []
