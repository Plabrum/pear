from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.matches.models import Match
from app.domain.messages.schemas import (
    Conversation,
    ConversationLastMessage,
    ConversationOther,
    Message,
    MessageSender,
)
from app.utils.sqids import Sqid

if TYPE_CHECKING:
    # Runtime imports here would close an import cycle: actions.deps ->
    # realtime.service -> realtime.channels -> messages.queries ->
    # messages.transformers. Annotations are lazy (`from __future__ import
    # annotations`), and `actions_for` is imported lazily inside the function.
    from app.platform.actions.base import ActionGroup
    from app.platform.actions.deps import ActionDeps


@dataclass
class MessageRow:
    id: Sqid
    match_id: Sqid
    sender_id: Sqid
    body: str
    is_read: bool
    created_at: datetime
    sender_chosen_name: str | None


@dataclass
class ConversationRow:
    match_id: Sqid
    match_created_at: datetime
    other_user_id: Sqid
    other_chosen_name: str | None
    last_message_id: Sqid | None
    last_message_body: str | None
    last_message_sender_id: Sqid | None
    last_message_is_read: bool | None
    last_message_created_at: datetime | None
    unread_count: int


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def row_to_message(row: MessageRow) -> Message:
    return Message(
        id=row.id,
        matchId=row.match_id,
        senderId=row.sender_id,
        body=row.body,
        isRead=row.is_read,
        createdAt=_iso(row.created_at) or "",
        sender=MessageSender(id=row.sender_id, chosenName=row.sender_chosen_name),
    )


def _row_to_last_message(row: ConversationRow) -> ConversationLastMessage | None:
    if (
        row.last_message_id is None
        or row.last_message_body is None
        or row.last_message_sender_id is None
        or row.last_message_is_read is None
        or row.last_message_created_at is None
    ):
        return None
    return ConversationLastMessage(
        id=row.last_message_id,
        body=row.last_message_body,
        senderId=row.last_message_sender_id,
        isRead=row.last_message_is_read,
        createdAt=_iso(row.last_message_created_at) or "",
    )


def row_to_conversation(
    row: ConversationRow,
    viewer_id: Sqid,
    group: ActionGroup,
    deps: ActionDeps,
) -> Conversation:
    convo = Conversation(
        matchId=row.match_id,
        createdAt=_iso(row.match_created_at) or "",
        other=ConversationOther(id=row.other_user_id, chosenName=row.other_chosen_name),
        lastMessage=_row_to_last_message(row),
        unreadCount=row.unread_count,
    )
    # Transient, scalar-only Match stub for membership gating (send / mark_read).
    # Never added to the session; MESSAGE_ACTIONS reads only user_a_id/user_b_id.
    match_stub = Match(id=row.match_id, user_a_id=viewer_id, user_b_id=row.other_user_id)
    # Call the group method directly (not the `actions_for` helper): importing
    # `app.platform.actions.hydrate` here would reintroduce the cycle this module
    # avoids. `group` is already injected, so no import is needed.
    convo.actions = group.get_available_actions(deps, obj=match_stub)
    return convo
