from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get
from litestar.exceptions import NotFoundException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.matches.queries import (
    fetch_match_other_user_id,
    fetch_matches,
    fetch_prompts_for_user,
    fetch_wing_note_for_match,
)
from app.domain.matches.schemas import MatchSheet, MatchSummary
from app.domain.matches.transformers import build_match_sheet, row_to_match
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient


class MatchesController(Controller):
    """GET /matches and GET /matches/{matchId}/sheet."""

    path = "/matches"

    @get("/", operation_id="getApiMatches")
    async def list_matches(self, user: User, transaction: AsyncSession, media: BaseMediaClient) -> list[MatchSummary]:
        rows = await fetch_matches(transaction, user.id)
        return [await row_to_match(r, media) for r in rows]

    @get("/{matchId:uuid}/sheet", operation_id="getApiMatchesMatchIdSheet")
    async def get_match_sheet(self, matchId: UUID, user: User, transaction: AsyncSession) -> MatchSheet:
        other_user_id = await fetch_match_other_user_id(transaction, user.id, matchId)
        if other_user_id is None:
            raise NotFoundException("Match not found")

        # These two reads share the request's single AsyncSession (which forbids
        # concurrent operations on one connection), so they run sequentially.
        wing_note_row = await fetch_wing_note_for_match(transaction, user.id, other_user_id)
        prompt_rows = await fetch_prompts_for_user(transaction, other_user_id)
        return build_match_sheet(wing_note_row, prompt_rows)


matches_router = Router(
    path="",
    route_handlers=[MatchesController],
    tags=["matches"],
    guards=[requires_session],
)
