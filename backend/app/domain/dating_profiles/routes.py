from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.exceptions import NotActiveWingpersonError
from app.domain.dating_profiles.queries import (
    fetch_likes_you_count,
    fetch_swipe_pool,
    is_active_wingperson,
)
from app.domain.dating_profiles.schemas import LikesYouCountResponse, SwipeProfile
from app.domain.dating_profiles.transformers import row_to_swipe_profile
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import resolve_group
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient
from app.utils.sqids import Sqid


class DatingProfilesSwipeController(Controller):
    """GET /dating-profiles/swipe (+ /swipe/count) — the collapsed swipe feed.

    One parametrized read on `DatingProfile` replacing discover / likes-you /
    wing-pool. The query params select the context:

      * default            -> the dater swipe feed (suggestions-first)
      * likesYouOnly=true  -> only candidates who liked the viewer (not matched)
      * wingerOnly=true    -> only candidates with a pending winger suggestion
      * filterWingerId     -> narrow wingerOnly to a single suggesting winger
      * daterId            -> the winger context (gated to an active wingperson)
    """

    path = "/dating-profiles/swipe"

    @get("/", operation_id="getApiDatingProfilesSwipe")
    async def get_swipe(
        self,
        user: User,
        transaction: AsyncSession,
        media: BaseMediaClient,
        action_deps: ActionDeps,
        page_size: int = Parameter(query="pageSize", default=20, ge=1, le=100),
        page_offset: int = Parameter(query="pageOffset", default=0, ge=0),
        likes_you_only: bool | None = Parameter(query="likesYouOnly", default=None, required=False),
        winger_only: bool | None = Parameter(query="wingerOnly", default=None, required=False),
        filter_winger_id: Sqid | None = Parameter(query="filterWingerId", default=None, required=False),
        dater_id: Sqid | None = Parameter(query="daterId", default=None, required=False),
    ) -> list[SwipeProfile]:
        # The winger context (daterId) is gated to an active wingperson, mirroring
        # the former wing-pool 403. RLS additionally scopes the underlying rows.
        if dater_id is not None and not await is_active_wingperson(transaction, user.id, dater_id):
            raise NotActiveWingpersonError

        rows = await fetch_swipe_pool(
            transaction,
            viewer_id=user.id,
            page_size=page_size,
            page_offset=page_offset,
            likes_you_only=bool(likes_you_only),
            winger_only=bool(winger_only),
            filter_winger_id=filter_winger_id,
            filter_dater_id=dater_id,
        )
        # Resolve the swipe action group ONCE per request (outside the row loop); each
        # row's actions are gated against a transient scalar-only stub in the transformer.
        swipe_group = resolve_group(ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS)
        return [await row_to_swipe_profile(r, media, swipe_group, action_deps) for r in rows]

    @get("/count", operation_id="getApiDatingProfilesSwipeCount")
    async def get_likes_you_count(self, user: User, transaction: AsyncSession) -> LikesYouCountResponse:
        count = await fetch_likes_you_count(transaction, user.id)
        return LikesYouCountResponse(count=count)


dating_profiles_router = Router(
    path="",
    route_handlers=[DatingProfilesSwipeController],
    tags=["dating-profiles"],
    guards=[requires_session],
)
