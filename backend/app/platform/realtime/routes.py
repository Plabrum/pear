from __future__ import annotations

import asyncio
import logging
import time

from litestar import WebSocket, websocket
from litestar.channels import ChannelsPlugin
from msgspec import json as _msgjson
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.realtime.channels import (
    TypingPairChannel,
    authorize_channel,
    parse_channel,
)
from app.platform.realtime.presence import presence_registry
from app.platform.realtime.schemas import (
    ErrorFrame,
    PongFrame,
    ReadyFrame,
    SubscribedFrame,
    UnsubscribedFrame,
)
from app.platform.realtime.service import RealtimeService
from app.utils.deps import rls_transaction

logger = logging.getLogger(__name__)

# TODO(#85): harden this multiplexed socket — access-token expiry mid-connection,
# client reconnect/resubscribe, send backpressure, presence ref-count on abrupt
# disconnect, live subscribe revocation, and a Redis backend for multi-replica.

# Close codes (4000-4999 are app-defined per RFC 6455).
WS_CLOSE_UNAUTHENTICATED = 4401

# Encode any msgspec struct -> JSON text for `socket.send_text`.
_encode = _msgjson.Encoder().encode


def _frame_text(frame: object) -> str:
    return _encode(frame).decode()


def _session_user_id(socket: WebSocket) -> int | None:
    """Read the authenticated principal's id from the session cookie on the handshake.

    SessionAuth runs on the upgrade (the `/ws` route is NOT excluded), so the
    rehydrated `User` principal is on `socket.user` / `socket.scope["user"]`. We
    take its id (an int — Sqid is an int subclass); no `?token=` fallback.
    """
    principal = socket.scope.get("user")
    user_id = getattr(principal, "id", None)
    return user_id if isinstance(user_id, int) else None


@websocket("/ws")
async def realtime_ws(
    socket: WebSocket,
    channels: ChannelsPlugin,
    # The raw (NOT request-scoped) DB session: the ws handler runs for the life of the
    # socket, so we wrap each authorize check in its own short-lived `rls_transaction`
    # scoped to the authenticated ws user rather than holding one tx open.
    db_session: AsyncSession,
) -> None:
    user_id = _session_user_id(socket)
    if user_id is None:
        await socket.accept()
        await socket.close(code=WS_CLOSE_UNAUTHENTICATED, reason="Unauthenticated")
        return

    await socket.accept()
    realtime = RealtimeService(channels)

    # channel -> the background pump task forwarding that channel's events to the socket.
    pumps: dict[str, asyncio.Task] = {}
    send_lock = asyncio.Lock()

    async def _send(text: str) -> None:
        # Serialize socket writes: the pump tasks + the inbound loop all send.
        async with send_lock:
            await socket.send_text(text)

    async def _pump(channel: str) -> None:
        """Forward every frame published to `channel` to this socket until cancelled."""
        async with channels.start_subscription(channel) as subscriber:
            async for event in subscriber.iter_events():
                # Events are already-encoded JSON bytes (see RealtimeService).
                await _send(event.decode() if isinstance(event, bytes) else event)

    async def _subscribe(channel: str) -> None:
        parsed = parse_channel(channel)
        if parsed is None:
            await _send(_frame_text(ErrorFrame(channel=channel, message="Unknown channel")))
            return
        if channel in pumps:
            await _send(_frame_text(SubscribedFrame(channel=channel)))  # idempotent ack
            return
        # RLS-equivalent gate, evaluated under an RLS-scoped tx set to this user.
        async with rls_transaction(db_session, user_id=user_id) as tx:
            allowed = await authorize_channel(tx, user_id, channel)
        if not allowed:
            await _send(_frame_text(ErrorFrame(channel=channel, message="Forbidden")))
            return
        pumps[channel] = asyncio.create_task(_pump(channel))
        await _send(_frame_text(SubscribedFrame(channel=channel)))

    async def _unsubscribe(channel: str) -> None:
        task = pumps.pop(channel, None)
        if task is not None:
            task.cancel()
        await _send(_frame_text(UnsubscribedFrame(channel=channel)))

    async def _typing(channel: str) -> None:
        parsed = parse_channel(channel)
        if not isinstance(parsed, TypingPairChannel):
            await _send(_frame_text(ErrorFrame(channel=channel, message="Not a typing channel")))
            return
        if user_id not in (parsed.a, parsed.b):
            await _send(_frame_text(ErrorFrame(channel=channel, message="Forbidden")))
            return
        other = parsed.b if parsed.a == user_id else parsed.a
        realtime.publish_typing(user_id, other, int(time.time() * 1000))

    # ── Presence: mark online + announce ────────────────────────────────────────
    became_online = presence_registry.connect(user_id)
    if became_online:
        _announce_presence(realtime, user_id, online=True)

    await _send(_frame_text(ReadyFrame()))

    try:
        async for raw in socket.iter_json():
            if not isinstance(raw, dict):
                await _send(_frame_text(ErrorFrame(message="Malformed frame")))
                continue
            kind = raw.get("type")
            match kind:
                case "subscribe":
                    channel = raw.get("channel")
                    if isinstance(channel, str):
                        await _subscribe(channel)
                    else:
                        await _send(_frame_text(ErrorFrame(message="subscribe requires a channel")))
                case "unsubscribe":
                    channel = raw.get("channel")
                    if isinstance(channel, str):
                        await _unsubscribe(channel)
                case "typing":
                    channel = raw.get("channel")
                    if isinstance(channel, str):
                        await _typing(channel)
                case "ping":
                    await _send(_frame_text(PongFrame()))
                case _:
                    await _send(_frame_text(ErrorFrame(message=f"Unknown frame type: {kind!r}")))
    except Exception:
        # Normal disconnects raise (WebSocketDisconnect); anything else we log.
        logger.debug("ws loop ended for user %s", user_id, exc_info=True)
    finally:
        for task in pumps.values():
            task.cancel()
        went_offline = presence_registry.disconnect(user_id)
        if went_offline:
            _announce_presence(realtime, user_id, online=False)


def _announce_presence(realtime: RealtimeService, user_id: int, *, online: bool) -> None:
    """Broadcast a presence change for `user_id` to the list channel + every peer's
    pair channel.

    The messages-list channel always gets the fresh full online set. For pair
    channels we publish to the pair this user shares with each OTHER currently-online
    user — that is the only set of pair channels whose `online` boolean changed and
    that has a live subscriber to receive it.
    """
    realtime.publish_messages_list_presence(presence_registry.online_ids(excluding=None))
    for other_id in presence_registry.online_ids(excluding=user_id):
        # Tell the peer's pair channel that THIS user's presence changed.
        realtime.publish_pair_presence(user_id, other_id, online=online)
        # And, on arrival, tell THIS user's freshly-opened pair channel that the
        # peer is already online (so a late joiner sees existing green dots).
        if online:
            realtime.publish_pair_presence(other_id, user_id, online=True)
