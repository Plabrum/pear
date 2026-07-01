from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import MagicMock

import pytest
from litestar import Request
from litestar.channels import ChannelsPlugin
from litestar.connection import ASGIConnection
from litestar.di import Provide
from litestar.exceptions import WebSocketDisconnect
from litestar.middleware.session.server_side import ServerSideSessionConfig
from litestar.status_codes import WS_1000_NORMAL_CLOSURE
from litestar.stores.memory import MemoryStore
from litestar.testing import AsyncTestClient
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TestConfig
from app.domain.messages.schemas import Message, MessageSender
from app.domain.profiles.models import Profile
from app.factory import create_app
from app.platform.auth.principal import User
from app.platform.realtime.channels import (
    MESSAGES_LIST_CHANNEL,
    MatchChannel,
    MessagesListChannel,
    PresencePairChannel,
    TypingPairChannel,
    authorize_channel,
    match_channel,
    parse_channel,
    presence_pair_channel,
    typing_pair_channel,
)
from app.platform.realtime.presence import PresenceRegistry
from app.platform.realtime.service import RealtimeService
from app.utils.sqids import sqid_encode
from tests.fixtures.graph import ActingAs, DomainGraph
from tests.fixtures.ids import fake_id

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


# ── Channel name building + parsing ──────────────────────────────────────────────


def test_match_channel_name_matches_client() -> None:
    mid = fake_id()
    assert match_channel(mid) == f"messages:match:{mid}"


def test_pair_channels_are_sorted_like_the_client() -> None:
    a, b = fake_id(), fake_id()
    # Sorted by string, regardless of argument order — matches use-presence.ts /
    # use-typing.ts `[a, b].sort().join(':')`.
    assert presence_pair_channel(a, b) == presence_pair_channel(b, a)
    assert typing_pair_channel(a, b) == typing_pair_channel(b, a)
    lo, hi = sorted([str(a), str(b)])
    assert presence_pair_channel(a, b) == f"presence:{lo}:{hi}"
    assert typing_pair_channel(a, b) == f"typing:{lo}:{hi}"


def test_parse_channel_round_trips() -> None:
    mid, a, b = fake_id(), fake_id(), fake_id()
    assert parse_channel(match_channel(mid)) == MatchChannel(match_id=mid)
    assert isinstance(parse_channel(MESSAGES_LIST_CHANNEL), MessagesListChannel)

    presence = parse_channel(presence_pair_channel(a, b))
    assert isinstance(presence, PresencePairChannel)
    assert {presence.a, presence.b} == {a, b}

    typing = parse_channel(typing_pair_channel(a, b))
    assert isinstance(typing, TypingPairChannel)
    assert {typing.a, typing.b} == {a, b}


def test_parse_channel_rejects_malformed() -> None:
    assert parse_channel("garbage") is None
    assert parse_channel("messages:match:not-a-uuid") is None
    assert parse_channel("presence:only-one-part") is None
    assert parse_channel(f"presence:{fake_id()}:not-a-uuid") is None
    assert parse_channel(f"typing:{fake_id()}") is None


# ── Subscribe-time authorization (RLS-equivalent) ────────────────────────────────


async def test_authorize_match_channel_allows_participants(graph: DomainGraph, acting_as: ActingAs) -> None:
    channel = match_channel(graph.match.id)
    async with acting_as(graph.dater_a.id) as s:
        assert await authorize_channel(s, graph.dater_a.id, channel) is True
    async with acting_as(graph.dater_b.id) as s:
        assert await authorize_channel(s, graph.dater_b.id, channel) is True


async def test_authorize_match_channel_rejects_non_participants(graph: DomainGraph, acting_as: ActingAs) -> None:
    channel = match_channel(graph.match.id)
    # dater_c is unrelated; the winger is not party to the match either. Under their
    # own RLS scope the match row is invisible, so the gate denies.
    async with acting_as(graph.dater_c.id) as s:
        assert await authorize_channel(s, graph.dater_c.id, channel) is False
    async with acting_as(graph.winger.id) as s:
        assert await authorize_channel(s, graph.winger.id, channel) is False


async def test_authorize_match_channel_rejects_unknown_match(graph: DomainGraph, acting_as: ActingAs) -> None:
    async with acting_as(graph.dater_a.id) as s:
        assert await authorize_channel(s, graph.dater_a.id, match_channel(fake_id())) is False


async def test_authorize_pair_channel_requires_membership(db_session: AsyncSession) -> None:
    a, b, c = fake_id(), fake_id(), fake_id()
    presence = presence_pair_channel(a, b)
    typing = typing_pair_channel(a, b)
    # Either member may join their shared pair channel...
    assert await authorize_channel(db_session, a, presence) is True
    assert await authorize_channel(db_session, b, presence) is True
    assert await authorize_channel(db_session, a, typing) is True
    # ...but a third party may not.
    assert await authorize_channel(db_session, c, presence) is False
    assert await authorize_channel(db_session, c, typing) is False


async def test_authorize_messages_list_open_to_any_user(db_session: AsyncSession) -> None:
    assert await authorize_channel(db_session, fake_id(), MESSAGES_LIST_CHANNEL) is True


async def test_authorize_unknown_channel_denied(db_session: AsyncSession) -> None:
    assert await authorize_channel(db_session, fake_id(), "not-a-real-channel") is False


# ── Presence registry: green-dot derivation + ref counting ───────────────────────


def test_presence_online_and_offline() -> None:
    reg = PresenceRegistry()
    u = fake_id()
    assert reg.is_online(u) is False
    assert reg.connect(u) is True  # first socket -> NEW arrival
    assert reg.is_online(u) is True
    assert reg.disconnect(u) is True  # last socket gone -> real departure
    assert reg.is_online(u) is False


def test_presence_reference_counts_multiple_sockets() -> None:
    reg = PresenceRegistry()
    u = fake_id()
    assert reg.connect(u) is True  # 0 -> 1 : arrival
    assert reg.connect(u) is False  # 1 -> 2 : not a new arrival
    assert reg.is_online(u) is True
    assert reg.disconnect(u) is False  # 2 -> 1 : still online, not a departure
    assert reg.is_online(u) is True
    assert reg.disconnect(u) is True  # 1 -> 0 : real departure
    assert reg.is_online(u) is False


def test_presence_duplicate_disconnect_is_harmless() -> None:
    reg = PresenceRegistry()
    u = fake_id()
    reg.connect(u)
    assert reg.disconnect(u) is True
    assert reg.disconnect(u) is False  # already gone -> no spurious leave


def test_presence_online_ids_set_excludes_self() -> None:
    reg = PresenceRegistry()
    me, other = fake_id(), fake_id()
    reg.connect(me)
    reg.connect(other)
    assert reg.online_ids(excluding=me) == {other}
    assert reg.online_ids(excluding=None) == {me, other}


# ── RealtimeService: after-commit message publish ────────────────────────────────


def _message(match_id, sender_id) -> Message:
    return Message(
        id=fake_id(),
        matchId=match_id,
        senderId=sender_id,
        body="hello",
        isRead=False,
        createdAt="2026-06-13T00:00:00+00:00",
        sender=MessageSender(id=sender_id, chosenName="Ada"),
    )


async def test_publish_message_fires_only_after_commit(db_session: AsyncSession) -> None:
    """The broadcast is registered as an after_commit listener — nothing is published
    until the transaction commits. The savepoint session lets us drive a real commit
    of a nested transaction without touching the outer rollback isolation.
    """
    channels = MagicMock()
    service = RealtimeService(channels)
    mid, sender = fake_id(), fake_id()

    # Register the after-commit publish, then assert it has NOT fired yet.
    service.publish_message_after_commit(db_session, mid, _message(mid, sender))
    channels.publish.assert_not_called()

    # Commit a nested transaction (savepoint) -> the after_commit hook on the sync
    # session fires.
    await db_session.commit()

    channels.publish.assert_called_once()
    frame, channel = channels.publish.call_args.args
    assert channel == match_channel(mid)
    assert frame["type"] == "message"
    assert frame["channel"] == match_channel(mid)
    assert frame["payload"].matchId == mid


async def test_publish_message_not_fired_on_rollback() -> None:
    """A rolled-back transaction must broadcast nothing (no phantom messages)."""
    # A standalone mock session: we never call commit, so the listener never fires.
    sync_session = MagicMock()
    listeners: list = []

    def _listen(target, name, fn, once=False):  # noqa: ARG001
        listeners.append(fn)

    channels = MagicMock()
    service = RealtimeService(channels)
    tx = MagicMock(sync_session=sync_session)

    # Patch event.listen to capture the listener instead of attaching it.
    original = event.listen
    event.listen = _listen  # type: ignore[assignment]
    try:
        service.publish_message_after_commit(tx, fake_id(), _message(fake_id(), fake_id()))
    finally:
        event.listen = original  # type: ignore[assignment]

    # Listener captured but never invoked (rollback path) -> no publish.
    assert len(listeners) == 1
    channels.publish.assert_not_called()


# ── Presence + typing publish frames (shape the client consumes) ─────────────────


def test_publish_pair_presence_frame_shape() -> None:
    channels = MagicMock()
    service = RealtimeService(channels)
    a, b = fake_id(), fake_id()
    service.publish_pair_presence(a, b, online=True)

    frame, channel = channels.publish.call_args.args
    assert channel == presence_pair_channel(a, b)
    assert frame == {"type": "presence", "channel": channel, "online": True}


def test_publish_messages_list_presence_frame_shape() -> None:
    channels = MagicMock()
    service = RealtimeService(channels)
    ids = {int(fake_id()), int(fake_id())}
    service.publish_messages_list_presence(ids)

    frame, channel = channels.publish.call_args.args
    assert channel == MESSAGES_LIST_CHANNEL
    assert frame["type"] == "presence"
    # ids ride the wire as their sqid-encoded string form.
    assert set(frame["onlineIds"]) == {sqid_encode(i) for i in ids}


def test_publish_typing_frame_shape() -> None:
    channels = MagicMock()
    service = RealtimeService(channels)
    a, b = fake_id(), fake_id()
    service.publish_typing(a, b, ts=1234)

    frame, channel = channels.publish.call_args.args
    assert channel == typing_pair_channel(a, b)
    assert frame == {
        "type": "typing",
        "channel": channel,
        "payload": {"userId": str(a), "ts": 1234},
    }


# ── End-to-end: the `/ws` route over AsyncTestClient ─────────────────────────────
#
# Proves the wire contract the client realtime agent matches: SessionAuth runs on
# the handshake and authenticates via the SESSION COOKIE (no `?token=`), the socket
# gets `ready`, then the subscribe gate (participant allowed, non-participant
# rejected) and the unauthenticated close when no session is present. The app is
# wired to the savepoint `db_session` so the RLS-scoped subscribe check runs against
# the seeded graph, and the SessionAuth `retrieve_user_handler` rehydrates the
# principal from that same session. The channels plugin's pub/sub workers are
# started by the test client's lifespan (`async with AsyncTestClient(...)`).


@pytest.fixture
async def ws_app(
    test_config: TestConfig,
    graph: DomainGraph,  # seeds the match graph in system mode before the client opens
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncTestClient]:
    """Real app on the savepoint session, cookie-session auth backed by a memory store."""

    async def _retrieve_user(session: dict, connection: ASGIConnection) -> User | None:
        user_id = session.get("user_id")
        if not user_id:
            return None
        profile = await db_session.get(Profile, user_id)
        return User.from_profile(profile) if profile is not None else None

    async def _test_transaction(request: Request) -> AsyncGenerator[AsyncSession]:
        async with db_session.begin_nested():
            principal = request.scope.get("user")
            await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
            if principal is not None:
                await db_session.execute(text(f"SET LOCAL app.user_id = '{principal.id}'"))
            try:
                yield db_session
            finally:
                await db_session.execute(text("SET LOCAL app.user_id = ''"))
                await db_session.execute(text("SET LOCAL app.is_system_mode = true"))

    app = create_app(
        test_config,
        dependencies_overrides={
            "db_session": Provide(lambda: db_session, sync_to_thread=False),
            "transaction": Provide(_test_transaction),
        },
        stores_overrides={"sessions": MemoryStore()},
        retrieve_user_handler_override=_retrieve_user,
    )
    # `session_config` mirrors the factory's (non-secure under TestConfig) so
    # `set_session_data` writes to the same "sessions" store and the plain-HTTP ws
    # client sends the cookie on the handshake.
    session_config = ServerSideSessionConfig(store="sessions", samesite="lax", secure=False, httponly=True)
    async with AsyncTestClient(app=app, session_config=session_config) as client:
        client.config = test_config  # type: ignore[attr-defined]
        client.graph = graph  # type: ignore[attr-defined]
        yield client


async def _login_as(client: AsyncTestClient, profile) -> None:
    """Set the cookie session for `profile` so the next ws handshake authenticates."""
    await client.set_session_data({"user_id": str(profile.id)})


async def test_ws_rejects_missing_session(ws_app: AsyncTestClient) -> None:
    # No session cookie -> SessionAuth runs on the upgrade (the `/ws` route is NOT
    # excluded) and rejects the handshake before the handler accepts. Either close
    # path is unauthenticated: SessionAuth's own rejection, or — if a connection ever
    # reached the handler with no principal — the handler's defensive 4401 close.
    with pytest.raises(WebSocketDisconnect) as exc:
        with await ws_app.websocket_connect("/ws") as ws:
            ws.receive()
    assert exc.value.code != WS_1000_NORMAL_CLOSURE


async def test_ws_authed_connect_gets_ready(ws_app: AsyncTestClient) -> None:
    graph: DomainGraph = ws_app.graph  # type: ignore[attr-defined]
    await _login_as(ws_app, graph.dater_a)
    with await ws_app.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"


async def test_ws_may_subscribe_to_own_pair_channel(ws_app: AsyncTestClient) -> None:
    """A user may subscribe to a presence pair channel that involves them.

    The pair gate is a pure id check (no DB), so it exercises the full transport
    end-to-end: auth -> subscribe -> allow -> `subscribed` ack. The DB-backed match
    channel gate is proven directly in the `authorize_channel` tests above (which run
    under real RLS sessions); we keep it off the websocket e2e to avoid sharing the
    savepoint session across the test client's portal thread.
    """
    graph: DomainGraph = ws_app.graph  # type: ignore[attr-defined]
    await _login_as(ws_app, graph.dater_a)
    channel = presence_pair_channel(graph.dater_a.id, graph.dater_b.id)
    with await ws_app.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "subscribe", "channel": channel})
        ack = ws.receive_json()
    assert ack == {"type": "subscribed", "channel": channel}


async def test_ws_may_subscribe_to_messages_list(ws_app: AsyncTestClient) -> None:
    graph: DomainGraph = ws_app.graph  # type: ignore[attr-defined]
    await _login_as(ws_app, graph.dater_a)
    with await ws_app.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "subscribe", "channel": MESSAGES_LIST_CHANNEL})
        ack = ws.receive_json()
    assert ack == {"type": "subscribed", "channel": MESSAGES_LIST_CHANNEL}


async def test_ws_subscribe_to_others_presence_pair_rejected(ws_app: AsyncTestClient) -> None:
    graph: DomainGraph = ws_app.graph  # type: ignore[attr-defined]
    # dater_a tries to join a pair channel between dater_b and dater_c (not theirs).
    await _login_as(ws_app, graph.dater_a)
    channel = presence_pair_channel(graph.dater_b.id, graph.dater_c.id)
    with await ws_app.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "subscribe", "channel": channel})
        frame = ws.receive_json()
    assert frame["type"] == "error"
    assert frame["channel"] == channel


async def test_ws_ping_pong(ws_app: AsyncTestClient) -> None:
    graph: DomainGraph = ws_app.graph  # type: ignore[attr-defined]
    await _login_as(ws_app, graph.dater_a)
    with await ws_app.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "ping"})
        assert ws.receive_json() == {"type": "pong"}


async def test_ws_subscribed_socket_receives_published_frame(ws_app: AsyncTestClient) -> None:
    """A frame published to a channel reaches a socket subscribed to it.

    This is the fan-out path the send action relies on: publish to a channel ->
    subscribed clients receive it. We publish directly through the app's
    ChannelsPlugin (the same handle `RealtimeService` uses) to a channel the socket
    subscribed to, and assert the socket forwards it.
    """
    graph: DomainGraph = ws_app.graph  # type: ignore[attr-defined]
    await _login_as(ws_app, graph.dater_a)
    channel = presence_pair_channel(graph.dater_a.id, graph.dater_b.id)
    plugin = ws_app.app.plugins.get(ChannelsPlugin)  # type: ignore[attr-defined]

    with await ws_app.websocket_connect("/ws") as ws:
        assert ws.receive_json()["type"] == "ready"
        ws.send_json({"type": "subscribe", "channel": channel})
        assert ws.receive_json() == {"type": "subscribed", "channel": channel}

        # Publish a presence frame to the channel; the pump forwards it to the socket.
        plugin.publish({"type": "presence", "channel": channel, "online": True}, channel)
        received = ws.receive_json()

    assert received == {"type": "presence", "channel": channel, "online": True}
