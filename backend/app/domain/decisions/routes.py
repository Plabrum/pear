from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.queries import fetch_my_suggestions, fetch_pending_suggestions
from app.domain.decisions.schemas import MySuggestion, PendingSuggestion
from app.domain.decisions.transformers import (
    row_to_pending_suggestion,
    transform_my_suggestion,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class DecisionsController(Controller):
    """GET /decisions/pending-suggestions and GET /decisions/my-suggestions."""

    path = "/decisions"

    @get("/pending-suggestions", operation_id="getApiDecisionsPendingSuggestions")
    async def get_pending_suggestions(self, user: User, transaction: AsyncSession) -> list[PendingSuggestion]:
        rows = await fetch_pending_suggestions(transaction, user.id)
        return [
            row_to_pending_suggestion(
                suggestion_id=sid,
                recipient_id=recipient_id,
                note=note,
                created_at=created_at,
                winger_id=winger_id,
                winger_name=winger_name,
            )
            for (sid, recipient_id, note, created_at, winger_id, winger_name) in rows
        ]

    @get("/my-suggestions", operation_id="getApiDecisionsMySuggestions")
    async def get_my_suggestions(
        self,
        user: User,
        transaction: AsyncSession,
        limit: int = Parameter(query="limit", default=50, ge=1, le=100),
    ) -> list[MySuggestion]:
        # Suggestions I made as a winger (`suggested_by = me`), with each card's
        # computed matched/pending/not_accepted status — the former people-activity feed.
        rows = await fetch_my_suggestions(transaction, user.id, limit)
        return [transform_my_suggestion(r) for r in rows]


decisions_router = Router(
    path="",
    route_handlers=[DecisionsController],
    tags=["decisions"],
    guards=[requires_session],
)
