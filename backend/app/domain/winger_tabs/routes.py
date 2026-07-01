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
