from __future__ import annotations

from app.platform.actions.schemas import Actionable
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── Messages ─────────────────────────────────────────────────────────────────


class MessageSender(BaseSchema):
    id: Sqid
    chosenName: str | None


class Message(BaseSchema):
    id: Sqid
    matchId: Sqid
    senderId: Sqid
    body: str
    isRead: bool
    createdAt: str
    sender: MessageSender | None


# GET /matches/{matchId}/messages returns an array of Message.
MessagesResponse = list[Message]


# ── Conversations ────────────────────────────────────────────────────────────


class ConversationOther(BaseSchema):
    id: Sqid
    chosenName: str | None


class ConversationLastMessage(BaseSchema):
    id: Sqid
    body: str
    senderId: Sqid
    isRead: bool
    createdAt: str


class Conversation(Actionable):
    matchId: Sqid
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
