from __future__ import annotations

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.queries import fetch_pending_suggestions
from app.domain.decisions.schemas import PendingSuggestion
from app.domain.decisions.transformers import row_to_pending_suggestion
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class DecisionsController(Controller):
    """GET /decisions/pending-suggestions."""

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


decisions_router = Router(
    path="",
    route_handlers=[DecisionsController],
    tags=["decisions"],
    guards=[requires_session],
)
