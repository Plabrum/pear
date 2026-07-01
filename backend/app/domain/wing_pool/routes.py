"""Read endpoint for the wing-pool domain (READS ONLY).

Ported from `supabase/functions/api/domains/wing-pool/route.ts` (GET /wing-pool).
Query-string-driven feed -> explicit `@get` handler on a Controller. The handler
asserts the caller is an ACTIVE wingperson for the requested dater (raising
`NotActiveWingpersonError` => 403, matching the Hono `HTTPException(403)`), then
runs the ported `fetch_wing_pool` and maps rows -> camelCase structs. No mutations.

`operation_id="getApiWingPool"` keeps the Orval-generated hook name stable.
"""

from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.discover.queries import fetch_wing_pool, is_active_wingperson
from app.domain.wing_pool.exceptions import NotActiveWingpersonError
from app.domain.wing_pool.schemas import WingProfile
from app.domain.wing_pool.transformers import row_to_wing_profile
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class WingPoolController(Controller):
    """GET /wing-pool — the dater-scoped pool a winger can suggest from."""

    path = "/wing-pool"

    @get("/", operation_id="getApiWingPool")
    async def get_wing_pool(
        self,
        user: User,
        transaction: AsyncSession,
        dater_id: UUID = Parameter(query="daterId"),
        page_size: int = Parameter(query="pageSize", default=20, ge=1, le=100),
        page_offset: int = Parameter(query="pageOffset", default=0, ge=0),
    ) -> list[WingProfile]:
        allowed = await is_active_wingperson(transaction, user.id, dater_id)
        if not allowed:
            raise NotActiveWingpersonError

        rows = await fetch_wing_pool(
            transaction,
            winger_id=user.id,
            dater_id=dater_id,
            page_size=page_size,
            page_offset=page_offset,
        )
        return [row_to_wing_profile(r) for r in rows]


wing_pool_router = Router(
    path="",
    route_handlers=[WingPoolController],
    tags=["wing-pool"],
    guards=[requires_session],
)
