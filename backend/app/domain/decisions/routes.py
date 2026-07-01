from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.queries import fetch_my_suggestions
from app.domain.decisions.schemas import MySuggestion
from app.domain.decisions.transformers import transform_my_suggestion
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class DecisionsController(Controller):
    """GET /decisions/my-suggestions."""

    path = "/decisions"

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
