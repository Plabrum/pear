from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.messages.actions import MarkMessagesRead, SendMessage
from app.domain.messages.models import Message
from app.domain.messages.queries import (
    fetch_conversations,
    fetch_messages_for_match,
    is_viewer_in_match,
)
from app.domain.messages.schemas import SendMessageData
from app.domain.messages.transformers import row_to_conversation, row_to_message
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(
    session: AsyncSession,
    *,
    user_id,
    role: Role = Role.DATER,
    push: object | None = None,
    realtime: object | None = None,
) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor."""
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=push if push is not None else MagicMock(send=AsyncMock()),
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
        realtime=realtime if realtime is not None else MagicMock(publish_message_after_commit=MagicMock()),
        media=MagicMock(),
    )


# ── Reads ──────────────────────────────────────────────────────────────────────


async def test_is_viewer_in_match(graph: DomainGraph, db_session: AsyncSession) -> None:
    assert await is_viewer_in_match(db_session, graph.dater_a.id, graph.match.id) is True
    assert await is_viewer_in_match(db_session, graph.dater_b.id, graph.match.id) is True
    # dater_c is not party to the match; the winger isn't either.
    assert await is_viewer_in_match(db_session, graph.dater_c.id, graph.match.id) is False
    assert await is_viewer_in_match(db_session, graph.winger.id, graph.match.id) is False
    # A non-existent match id is also "not in match".
    assert await is_viewer_in_match(db_session, graph.dater_a.id, uuid4()) is False


async def test_list_messages_chronological_with_sender(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_messages_for_match(db_session, graph.match.id, 50, 0)
    dtos = [row_to_message(r) for r in rows]

    # graph seeds exactly one message, sent by dater_a.
    assert len(dtos) == 1
    msg = dtos[0]
    assert msg.matchId == graph.match.id
    assert msg.senderId == graph.dater_a.id
    assert msg.isRead is False
    assert msg.body == graph.message.body
    # sender ref carries the chosen name (left-joined profiles).
    assert msg.sender is not None
    assert msg.sender.id == graph.dater_a.id
    assert msg.sender.chosenName == graph.dater_a.chosen_name
    # createdAt is an ISO string (timestamptz -> JSON contract).
    assert isinstance(msg.createdAt, str) and msg.createdAt


async def test_list_messages_pagination(graph: DomainGraph, db_session: AsyncSession) -> None:
    # offset past the single seeded message -> empty page.
    rows = await fetch_messages_for_match(db_session, graph.match.id, 50, 5)
    assert rows == []


async def test_list_conversations(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_conversations(db_session, graph.dater_a.id)
    dtos = [row_to_conversation(r) for r in rows]

    # dater_a is party to exactly one match (with dater_b).
    assert len(dtos) == 1
    convo = dtos[0]
    assert convo.matchId == graph.match.id
    # "other" is dater_b, with their chosen name.
    assert convo.other.id == graph.dater_b.id
    assert convo.other.chosenName == graph.dater_b.chosen_name
    # last message is the one dater_a sent.
    assert convo.lastMessage is not None
    assert convo.lastMessage.id == graph.message.id
    assert convo.lastMessage.senderId == graph.dater_a.id
    assert convo.lastMessage.body == graph.message.body
    # The only message is OUTBOUND for dater_a -> unread count is 0.
    assert convo.unreadCount == 0


async def test_list_conversations_unread_count_for_recipient(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The seeded message is inbound for dater_b (sender is dater_a) and unread.
    rows = await fetch_conversations(db_session, graph.dater_b.id)
    dtos = [row_to_conversation(r) for r in rows]
    assert len(dtos) == 1
    assert dtos[0].other.id == graph.dater_a.id
    assert dtos[0].unreadCount == 1


# ── Actions: happy path ─────────────────────────────────────────────────────────


async def test_send_message_inserts_and_pushes(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Give dater_b a push token so the recipient push path is exercised.
    graph.dater_b.push_token = "ExpoPushToken[recipient]"
    await db_session.flush()

    push = MagicMock(send=AsyncMock())
    deps = _deps(db_session, user_id=graph.dater_a.id, push=push)
    data = SendMessageData(body="Hey there, nice to match!")

    assert SendMessage.is_available(graph.match, deps) is True
    result = await SendMessage.execute(graph.match, data, db_session, deps)

    assert result.message == "Message sent"
    assert result.created_id is not None

    rows = await fetch_messages_for_match(db_session, graph.match.id, 50, 0)
    assert len(rows) == 2  # the seeded one + the new one
    # (created_at can tie at the transaction clock, so match by id, not position.)
    inserted = next(r for r in rows if r.id == result.created_id)
    assert inserted.body == "Hey there, nice to match!"
    assert inserted.sender_id == graph.dater_a.id

    # Recipient (dater_b) was pushed with the sender name + preview.
    push.send.assert_awaited_once()
    token, title, body = push.send.await_args.args
    assert token == "ExpoPushToken[recipient]"
    assert graph.dater_a.chosen_name in title
    assert body == "Hey there, nice to match!"


async def test_send_message_publishes_to_match_channel_after_commit(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    """The send action schedules a realtime broadcast of the new message to the
    match channel (the after-commit publish).
    """
    realtime = MagicMock(publish_message_after_commit=MagicMock())
    deps = _deps(db_session, user_id=graph.dater_a.id, realtime=realtime)

    result = await SendMessage.execute(graph.match, SendMessageData(body="live!"), db_session, deps)

    # Broadcast was scheduled once, for THIS match, carrying the inserted message DTO.
    realtime.publish_message_after_commit.assert_called_once()
    tx_arg, match_id_arg, message_dto = realtime.publish_message_after_commit.call_args.args
    assert tx_arg is db_session
    assert match_id_arg == graph.match.id
    # The DTO is the camelCase Message the client consumes (matchId/senderId/body).
    assert message_dto.id == result.created_id
    assert message_dto.matchId == graph.match.id
    assert message_dto.senderId == graph.dater_a.id
    assert message_dto.body == "live!"


async def test_send_message_truncates_long_preview(graph: DomainGraph, db_session: AsyncSession) -> None:
    graph.dater_b.push_token = "ExpoPushToken[recipient]"
    await db_session.flush()

    push = MagicMock(send=AsyncMock())
    deps = _deps(db_session, user_id=graph.dater_a.id, push=push)
    long_body = "x" * 200
    await SendMessage.execute(graph.match, SendMessageData(body=long_body), db_session, deps)

    _token, _title, body = push.send.await_args.args
    # The preview truncates to 77 chars + ellipsis when the body exceeds 80.
    assert body == "x" * 77 + "…"


async def test_send_message_skips_push_when_no_token(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b has no push token by default -> push.send is not called.
    push = MagicMock(send=AsyncMock())
    deps = _deps(db_session, user_id=graph.dater_a.id, push=push)
    await SendMessage.execute(graph.match, SendMessageData(body="hi"), db_session, deps)
    push.send.assert_not_awaited()


async def test_mark_messages_read_flips_inbound(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The seeded message is inbound + unread for dater_b.
    deps = _deps(db_session, user_id=graph.dater_b.id)
    assert MarkMessagesRead.is_available(graph.match, deps) is True

    result = await MarkMessagesRead.execute(graph.match, EmptyActionData(), db_session, deps)
    assert "1" in result.message

    refreshed = (await db_session.execute(select(Message).where(Message.id == graph.message.id))).scalar_one()
    assert refreshed.is_read is True


async def test_mark_messages_read_does_not_touch_own_outbound(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a SENT the only message — marking read as the sender flips nothing.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    result = await MarkMessagesRead.execute(graph.match, EmptyActionData(), db_session, deps)
    assert "0" in result.message

    refreshed = (await db_session.execute(select(Message).where(Message.id == graph.message.id))).scalar_one()
    assert refreshed.is_read is False


# ── Actions: gate denials ───────────────────────────────────────────────────────


async def test_send_message_denied_for_non_party(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is not on the match -> is_available is False, surfaced as
    # PermissionDenied by the action router before execute runs.
    deps = _deps(db_session, user_id=graph.dater_c.id)
    assert SendMessage.is_available(graph.match, deps) is False


async def test_mark_messages_read_denied_for_non_party(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert MarkMessagesRead.is_available(graph.match, deps) is False
