from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.matches.models import Match
from app.domain.messages.queries import (
    fetch_push_token,
    get_match_peers,
    insert_message,
    mark_messages_read,
)
from app.domain.messages.schemas import SendMessageData
from app.domain.messages.transformers import row_to_message
from app.platform.actions.base import (
    BaseObjectAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from app.platform.auth.principal import User

# ── Action group ──────────────────────────────────────────────────────────────


class MessageActionKey(StrEnum):
    SEND = "send"
    MARK_READ = "mark_read"


message_actions = action_group_factory(
    ActionGroupType.MESSAGE_ACTIONS,
    default_invalidation="/conversations",
    model_type=Match,
)


def _viewer_in_match(match: Match, user: User) -> bool:
    """The actor must be one of the two matched users."""
    return user.id in (match.user_a_id, match.user_b_id)


# ── POST /matches/{matchId}/messages ──────────────────────────────────────────


@message_actions
class SendMessage(BaseObjectAction[Match, SendMessageData]):
    action_key: ClassVar[MessageActionKey] = MessageActionKey.SEND
    label = "Send Message"
    icon = ActionIcon.SEND

    @classmethod
    def is_available(cls, obj: Match, user: User, deps: ActionDeps) -> bool:
        return _viewer_in_match(obj, user)

    @classmethod
    async def execute(
        cls,
        obj: Match,
        data: SendMessageData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        viewer_id = user.id
        row = await insert_message(transaction, obj.id, viewer_id, data.body)

        # Push the recipient: "New message from <name>: <preview>".
        peers = await get_match_peers(transaction, obj.id)
        if peers is not None:
            user_a_id, user_b_id = peers
            recipient_id = user_b_id if user_a_id == viewer_id else user_a_id
            recipient_token = await fetch_push_token(transaction, recipient_id)
            if recipient_token is not None:
                sender_name = row.sender_chosen_name or "Someone"
                preview = data.body if len(data.body) <= 80 else data.body[:77] + "…"
                await deps.push.send(recipient_token, f"New message from {sender_name}", preview)

        # Live messages: broadcast the new message to the match channel AFTER COMMIT
        # so a subscribed peer's open conversation updates live. The publish is
        # registered as a one-shot `after_commit` listener — a rolled-back request
        # broadcasts nothing, and a subscriber never sees an id before the row is
        # durable. `realtime` is always injected on the request path; the guard is
        # only for unit tests that build ActionDeps without it.
        if deps.realtime is not None:
            deps.realtime.publish_message_after_commit(transaction, obj.id, row_to_message(row))

        return ActionExecutionResponse(
            message="Message sent",
            invalidate_queries=["/messages", "/conversations"],
            created_id=row.id,
        )


# ── POST /matches/{matchId}/messages/read ─────────────────────────────────────


@message_actions
class MarkMessagesRead(BaseObjectAction[Match, EmptyActionData]):
    action_key: ClassVar[MessageActionKey] = MessageActionKey.MARK_READ
    label = "Mark Read"
    icon = ActionIcon.CHECK

    @classmethod
    def is_available(cls, obj: Match, user: User, deps: ActionDeps) -> bool:
        return _viewer_in_match(obj, user)

    @classmethod
    async def execute(
        cls,
        obj: Match,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        updated = await mark_messages_read(transaction, obj.id, user.id)
        return ActionExecutionResponse(
            message=f"Marked {updated} message(s) read",
            invalidate_queries=["/messages", "/conversations"],
        )
