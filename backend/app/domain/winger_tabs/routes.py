"""Read endpoint for the winger-tabs domain (READS ONLY).

Ported from `supabase/functions/api/domains/winger-tabs/route.ts`:
  * GET /winger-tabs -> distinct wingers with a pending suggestion for the viewer,
    most-recent first.

A single dedup-and-order aggregate, not a list/detail-by-id resource, so it is an
explicit `@get` handler on a `Controller` taking the injected RLS-scoped
`transaction` and authenticated `user` rather than the declarative
`make_crud_controller`. There is no `actions.py`: this domain is read-only.

`operation_id` (`getApiWingerTabs`) keeps the Orval hook name stable across the
Hono -> Litestar cutover.
"""

from __future__ import annotations

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.winger_tabs.queries import fetch_winger_tabs
from app.domain.winger_tabs.schemas import WingerTab
from app.domain.winger_tabs.transformers import rows_to_winger_tabs
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class WingerTabsController(Controller):
    """GET /winger-tabs."""

    path = "/winger-tabs"

    @get("/", operation_id="getApiWingerTabs")
    async def get_winger_tabs(self, user: User, transaction: AsyncSession) -> list[WingerTab]:
        rows = await fetch_winger_tabs(transaction, user.id)
        return rows_to_winger_tabs(rows)


winger_tabs_router = Router(
    path="",
    route_handlers=[WingerTabsController],
    tags=["winger-tabs"],
    guards=[requires_session],
)
