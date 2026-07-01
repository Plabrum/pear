"""Read endpoints for the contacts (wingperson roster) domain (READS ONLY).

Ported from the GET handler in `supabase/functions/api/domains/contacts/route.ts`.
All mutations (invite / accept / decline / remove) live in `actions.py`.

The single read — GET /wingpeople — is a *combined* view: the caller's active
wingpeople, their incoming invitations (as a winger), the daters they are winging
for, the invitations they have sent (as a dater), and a per-contact weekly
suggestion count. That is a custom aggregate, not a list/detail CRUD resource, so
it is an explicit `@get` handler on a `Controller` (taking the injected RLS-scoped
`transaction` + the authenticated `user`) rather than the declarative
`make_crud_controller`. RLS enforces access; the queries assemble the right slice
of the caller's own contacts for each list.
"""

from __future__ import annotations

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.queries import (
    fetch_active_wingpeople,
    fetch_incoming_invitations,
    fetch_sent_invitations,
    fetch_weekly_counts,
    fetch_winging_for,
)
from app.domain.contacts.schemas import WingpeopleResponse
from app.domain.contacts.transformers import (
    row_to_incoming_invitation,
    row_to_sent_invitation,
    row_to_winging_for,
    row_to_wingperson,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class WingpeopleController(Controller):
    """GET /wingpeople — the combined wingperson roster bundle."""

    path = "/wingpeople"

    @get("/", operation_id="getApiWingpeople")
    async def get_wingpeople(self, user: User, transaction: AsyncSession) -> WingpeopleResponse:
        wingpeople = await fetch_active_wingpeople(transaction, user.id)
        invitations = await fetch_incoming_invitations(transaction, user.id)
        sent_invitations = await fetch_sent_invitations(transaction, user.id)
        winging_for = await fetch_winging_for(transaction, user.id)
        weekly_counts = await fetch_weekly_counts(transaction, user.id, wingpeople)

        return WingpeopleResponse(
            wingpeople=[row_to_wingperson(r) for r in wingpeople],
            invitations=[row_to_incoming_invitation(r) for r in invitations],
            wingingFor=[row_to_winging_for(r) for r in winging_for],
            sentInvitations=[row_to_sent_invitation(r) for r in sent_invitations],
            weeklyCounts=weekly_counts,
        )


contacts_router = Router(
    path="",
    route_handlers=[WingpeopleController],
    tags=["contacts"],
    guards=[requires_session],
)
