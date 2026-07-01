from __future__ import annotations

from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── Messages ─────────────────────────────────────────────────────────────────


class MessageSender(BaseSchema):
    id: UUID
    chosenName: str | None


class Message(BaseSchema):
    id: UUID
    matchId: UUID
    senderId: UUID
    body: str
    isRead: bool
    createdAt: str
    sender: MessageSender | None


# GET /matches/{matchId}/messages returns an array of Message.
MessagesResponse = list[Message]


# ── Conversations ────────────────────────────────────────────────────────────


class ConversationOther(BaseSchema):
    id: UUID
    chosenName: str | None


class ConversationLastMessage(BaseSchema):
    id: UUID
    body: str
    senderId: UUID
    isRead: bool
    createdAt: str


class Conversation(BaseSchema):
    matchId: UUID
    createdAt: str
    other: ConversationOther
    lastMessage: ConversationLastMessage | None
    unreadCount: int


# GET /conversations returns an array of Conversation.
ConversationsResponse = list[Conversation]


# ── Inputs ───────────────────────────────────────────────────────────────────


class SendMessageData(BaseSchema):
    """POST /matches/{matchId}/messages body."""

    body: str


# ── Misc responses ───────────────────────────────────────────────────────────


class MarkMessagesReadResponse(BaseSchema):
    updated: int
