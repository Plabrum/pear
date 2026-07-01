from __future__ import annotations

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.queries import (
    fetch_active_wingpeople,
    fetch_incoming_invitations,
    fetch_sent_invitations,
    fetch_weekly_counts,
    fetch_winging_for,
    fetch_winging_for_tabs,
)
from app.domain.contacts.schemas import WingingForTabsResponse, WingpeopleResponse
from app.domain.contacts.transformers import (
    row_to_incoming_invitation,
    row_to_sent_invitation,
    row_to_winging_for,
    row_to_wingperson,
    rows_to_winging_for_tabs,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient


class WingpeopleController(Controller):
    """GET /wingpeople — the combined wingperson roster bundle."""

    path = "/wingpeople"

    @get("/", operation_id="getApiWingpeople")
    async def get_wingpeople(self, user: User, transaction: AsyncSession, media: BaseMediaClient) -> WingpeopleResponse:
        wingpeople = await fetch_active_wingpeople(transaction, user.id)
        invitations = await fetch_incoming_invitations(transaction, user.id)
        sent_invitations = await fetch_sent_invitations(transaction, user.id)
        winging_for = await fetch_winging_for(transaction, user.id)
        weekly_counts = await fetch_weekly_counts(transaction, user.id, wingpeople)

        return WingpeopleResponse(
            wingpeople=[row_to_wingperson(r, media) for r in wingpeople],
            invitations=[row_to_incoming_invitation(r) for r in invitations],
            wingingFor=[row_to_winging_for(r, media) for r in winging_for],
            sentInvitations=[row_to_sent_invitation(r) for r in sent_invitations],
            weeklyCounts=weekly_counts,
        )


class WingerTabsController(Controller):
    """GET /winger-tabs — the daters the caller actively wings for."""

    path = "/winger-tabs"

    @get("/", operation_id="getApiWingerTabs")
    async def get_winger_tabs(self, user: User, transaction: AsyncSession) -> WingingForTabsResponse:
        """My active winger-side edges, collapsed to a distinct `{id, name}` dater list."""
        rows = await fetch_winging_for_tabs(transaction, user.id)
        return rows_to_winging_for_tabs(rows)


contacts_router = Router(
    path="",
    route_handlers=[WingpeopleController, WingerTabsController],
    tags=["contacts"],
    guards=[requires_session],
)
