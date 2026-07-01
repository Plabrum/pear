from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from litestar.channels import ChannelsPlugin
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.messages.schemas import Message
from app.platform.realtime.channels import (
    MESSAGES_LIST_CHANNEL,
    match_channel,
    presence_pair_channel,
    typing_pair_channel,
)

logger = logging.getLogger(__name__)


class RealtimeService:
    def __init__(self, channels: ChannelsPlugin) -> None:
        self._channels = channels

    # ── Live messages ──────────────────────────────────────────────────────────

    def _message_frame(self, match_id: UUID, message: Message) -> dict[str, Any]:
        return {
            "type": "message",
            "channel": match_channel(match_id),
            "payload": message,
        }

    def publish_message_after_commit(
        self,
        transaction: AsyncSession,
        match_id: UUID,
        message: Message,
    ) -> None:
        """Broadcast a new message to its match channel AFTER the tx commits.

        Registers a one-shot `after_commit` listener on the request's session so the
        frame goes out only once the row is durable. A rolled-back request fires
        nothing.
        """
        frame = self._message_frame(match_id, message)
        channel = match_channel(match_id)

        def _listener(_session: Any) -> None:
            try:
                self._channels.publish(frame, channel)
            except Exception:
                # Never let a realtime publish failure surface — the message is
                # already committed; clients fall back to refetch-on-focus.
                logger.exception("Failed to publish message to channel %s", channel)

        event.listen(transaction.sync_session, "after_commit", _listener, once=True)

    # ── Presence ───────────────────────────────────────────────────────────────

    def publish_pair_presence(self, viewer_id: UUID, other_id: UUID, *, online: bool) -> None:
        """Tell `other_id`'s pair channel whether `viewer_id` is online.

        The frame is keyed to the SORTED pair channel both peers share; the client's
        `use-presence.ts` reads `online` directly (re-derived green dot).
        """
        channel = presence_pair_channel(viewer_id, other_id)
        self._channels.publish(
            {"type": "presence", "channel": channel, "online": online},
            channel,
        )

    def publish_messages_list_presence(self, online_ids: set[UUID]) -> None:
        """Broadcast the full online set to the messages-list channel.

        Mirrors `use-messages-list-presence.ts`, which consumed a `Set<string>`. The
        client filters its own id out; we also exclude it at the call site.
        """
        self._channels.publish(
            {
                "type": "presence",
                "channel": MESSAGES_LIST_CHANNEL,
                "onlineIds": [str(uid) for uid in online_ids],
            },
            MESSAGES_LIST_CHANNEL,
        )

    # ── Typing ─────────────────────────────────────────────────────────────────

    def publish_typing(self, viewer_id: UUID, other_id: UUID, ts: int) -> None:
        """Transient typing event over the sorted pair channel (`use-typing.ts`)."""
        channel = typing_pair_channel(viewer_id, other_id)
        self._channels.publish(
            {
                "type": "typing",
                "channel": channel,
                "payload": {"userId": str(viewer_id), "ts": ts},
            },
            channel,
        )
