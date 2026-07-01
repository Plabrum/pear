from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.messages.schemas import (
    Conversation,
    ConversationLastMessage,
    ConversationOther,
    Message,
    MessageSender,
)


@dataclass
class MessageRow:
    id: UUID
    match_id: UUID
    sender_id: UUID
    body: str
    is_read: bool
    created_at: datetime
    sender_chosen_name: str | None


@dataclass
class ConversationRow:
    match_id: UUID
    match_created_at: datetime
    other_user_id: UUID
    other_chosen_name: str | None
    last_message_id: UUID | None
    last_message_body: str | None
    last_message_sender_id: UUID | None
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


def row_to_conversation(row: ConversationRow) -> Conversation:
    return Conversation(
        matchId=row.match_id,
        createdAt=_iso(row.match_created_at) or "",
        other=ConversationOther(id=row.other_user_id, chosenName=row.other_chosen_name),
        lastMessage=_row_to_last_message(row),
        unreadCount=row.unread_count,
    )
