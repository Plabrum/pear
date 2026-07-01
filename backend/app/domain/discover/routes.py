"""Read endpoint for the discover domain (READS ONLY).

Ported from `supabase/functions/api/domains/discover/route.ts` (GET /discover).
This feed is query-string-driven (not a list/detail-by-id resource), so it is an
explicit `@get` handler on a Controller rather than the declarative
`make_crud_controller`. The handler takes the RLS-scoped `transaction` and the
authenticated `user`, runs the ported `fetch_discover_pool`, and maps rows ->
camelCase structs. No mutations live here (there are none for this domain).

`operation_id="getApiDiscover"` keeps the Orval-generated hook name stable across
the Hono -> Litestar cutover.
"""

from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.discover.queries import fetch_discover_pool
from app.domain.discover.schemas import DiscoverProfile
from app.domain.discover.transformers import row_to_discover_profile
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class DiscoverController(Controller):
    """GET /discover — the dater swipe feed for the viewer."""

    path = "/discover"

    @get("/", operation_id="getApiDiscover")
    async def get_discover(
        self,
        user: User,
        transaction: AsyncSession,
        page_size: int = Parameter(query="pageSize", default=20, ge=1, le=100),
        page_offset: int = Parameter(query="pageOffset", default=0, ge=0),
        filter_winger_id: UUID | None = Parameter(query="filterWingerId", default=None, required=False),
        winger_only: bool | None = Parameter(query="wingerOnly", default=None, required=False),
        likes_you_only: bool | None = Parameter(query="likesYouOnly", default=None, required=False),
    ) -> list[DiscoverProfile]:
        rows = await fetch_discover_pool(
            transaction,
            viewer_id=user.id,
            page_size=page_size,
            page_offset=page_offset,
            filter_winger_id=filter_winger_id,
            winger_only=bool(winger_only),
            likes_you_only=bool(likes_you_only),
        )
        return [row_to_discover_profile(r) for r in rows]


discover_router = Router(
    path="",
    route_handlers=[DiscoverController],
    tags=["discover"],
    guards=[requires_session],
)
