"""msgspec schemas for the messages domain.

Ported from `supabase/functions/api/domains/messages/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hooks
consume these.

Output structs:
  * `Message`        — one chat message (with its `sender` ref)         -> messages list / send
  * `Conversation`   — one match row with last message + unread count   -> conversations list

Input structs (consumed by the actions layer):
  * `SendMessageData`          — POST /matches/{matchId}/messages body  (`{ body }`)
  * (mark-read takes no body — `EmptyActionData` in actions.py)

`MarkMessagesReadResponse` mirrors Hono's `{ updated }` shape; the action returns the
count via the generic `ActionExecutionResponse.message`, but the struct is kept for
the documented contract / reuse.
"""

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
