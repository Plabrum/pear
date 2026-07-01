"""Read endpoints for the messages domain (READS ONLY).

Ported from the GET handlers in `supabase/functions/api/domains/messages/route.ts`.
All mutations (send / mark-read) live in `actions.py`.

Both reads are custom-shaped (a parent-filtered message list under a match path, and
a per-match conversation aggregate), so they are explicit `@get` handlers on a
`Controller` rather than the declarative `make_crud_controller` (which assumes
list-by-body + detail-by-row-id). Each handler takes the injected RLS-scoped
`transaction` and the authenticated `user`.

Access is RLS-enforced (the messages/matches SELECT policies gate the viewer to
matches they are party to). The list-messages handler additionally calls
`is_viewer_in_match` and raises `MatchNotFoundError` (404) when the viewer is not a
party — preserving the Hono route's explicit 404 for "match not found OR not party",
which collapses the empty-result case into a not-found rather than an empty array.
"""

from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.messages.exceptions import MatchNotFoundError
from app.domain.messages.queries import (
    fetch_conversations,
    fetch_messages_for_match,
    is_viewer_in_match,
)
from app.domain.messages.schemas import ConversationsResponse, MessagesResponse
from app.domain.messages.transformers import row_to_conversation, row_to_message
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class MessagesController(Controller):
    """GET /matches/{matchId}/messages and GET /conversations."""

    path = ""

    @get("/matches/{matchId:uuid}/messages", operation_id="getApiMatchesMatchIdMessages")
    async def list_messages(
        self,
        matchId: UUID,
        user: User,
        transaction: AsyncSession,
        limit: int = 50,
        offset: int = 0,
    ) -> MessagesResponse:
        allowed = await is_viewer_in_match(transaction, user.id, matchId)
        if not allowed:
            raise MatchNotFoundError()

        # Clamp to the Hono Zod bounds (limit 1..200, offset >= 0).
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        rows = await fetch_messages_for_match(transaction, matchId, limit, offset)
        return [row_to_message(r) for r in rows]

    @get("/conversations", operation_id="getApiConversations")
    async def list_conversations(self, user: User, transaction: AsyncSession) -> ConversationsResponse:
        rows = await fetch_conversations(transaction, user.id)
        return [row_to_conversation(r) for r in rows]


messages_router = Router(
    path="",
    route_handlers=[MessagesController],
    tags=["messages"],
    guards=[requires_session],
)
