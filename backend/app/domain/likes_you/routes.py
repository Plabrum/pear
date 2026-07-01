from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.discover.queries import fetch_likes_you_count, fetch_likes_you_pool
from app.domain.likes_you.schemas import LikesYouCountResponse, LikesYouProfile
from app.domain.likes_you.transformers import row_to_likes_you_profile
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient


class LikesYouController(Controller):
    """GET /likes-you and GET /likes-you/count."""

    path = "/likes-you"

    @get("/", operation_id="getApiLikesYou")
    async def get_likes_you(
        self,
        user: User,
        transaction: AsyncSession,
        media: BaseMediaClient,
        page_size: int = Parameter(query="pageSize", default=20, ge=1, le=100),
        page_offset: int = Parameter(query="pageOffset", default=0, ge=0),
    ) -> list[LikesYouProfile]:
        rows = await fetch_likes_you_pool(
            transaction,
            viewer_id=user.id,
            page_size=page_size,
            page_offset=page_offset,
        )
        return [await row_to_likes_you_profile(r, media) for r in rows]

    @get("/count", operation_id="getApiLikesYouCount")
    async def get_likes_you_count(self, user: User, transaction: AsyncSession) -> LikesYouCountResponse:
        count = await fetch_likes_you_count(transaction, user.id)
        return LikesYouCountResponse(count=count)


likes_you_router = Router(
    path="",
    route_handlers=[LikesYouController],
    tags=["likes-you"],
    guards=[requires_session],
)
