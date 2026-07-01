"""Read endpoints for the profiles domain (READS ONLY).

Ported from the GET handlers in `supabase/functions/api/domains/profiles/route.ts`.
All mutations live in `actions.py`.

This domain's reads are custom-shaped — "self" singletons (`/profiles/me`,
`/dating-profiles/me`) and a public-by-user-id detail (`/profiles/{userId}`) — so
they are explicit `@get` handlers on a `Controller` rather than the declarative
`make_crud_controller` (which assumes list + detail-by-row-id). Each handler takes
the injected RLS-scoped `transaction` and the authenticated `user`; RLS enforces
access (e.g. the public profile is gated by the profiles SELECT policy), and the
transformers map ORM rows -> camelCase structs.

For a domain whose reads ARE list/detail-shaped (a parent-filtered collection of
rows keyed by `id`), the pattern is instead::

    config = CRUDConfig(model=Foo, to_list_item=_to_list_item, to_detail=_to_detail,
                        scope="user", filterable_columns={"parent_id"})
    FooController = make_crud_controller("", config)

with `_to_list_item(obj, user)` / `_to_detail(obj, user)` transformers. See the
returned interface notes for the copyable shape.
"""

from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get
from litestar.exceptions import NotFoundException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.profiles.queries import (
    fetch_own_dating_profile,
    fetch_profile,
    fetch_public_profile,
)
from app.domain.profiles.schemas import (
    OwnDatingProfileResponse,
    Profile,
    PublicProfile,
)
from app.domain.profiles.transformers import (
    bundle_to_public_profile,
    dating_profile_to_own,
    row_to_profile,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class ProfilesController(Controller):
    """GET /profiles/me and GET /profiles/{userId}."""

    path = "/profiles"

    @get("/me", operation_id="getApiProfilesMe")
    async def get_own_profile(self, user: User, transaction: AsyncSession) -> Profile:
        row = await fetch_profile(transaction, user.id)
        if row is None:
            raise NotFoundException("Profile not found")
        return row_to_profile(row)

    @get("/{userId:uuid}", operation_id="getApiProfilesUserId")
    async def get_public_profile(self, userId: UUID, user: User, transaction: AsyncSession) -> PublicProfile:
        bundle = await fetch_public_profile(transaction, userId)
        if bundle is None:
            raise NotFoundException("Profile not found")
        profile, base, photos, prompts = bundle
        return bundle_to_public_profile(profile, base, photos, prompts)


class DatingProfilesController(Controller):
    """GET /dating-profiles/me."""

    path = "/dating-profiles"

    @get("/me", operation_id="getApiDatingProfilesMe")
    async def get_own_dating_profile(self, user: User, transaction: AsyncSession) -> OwnDatingProfileResponse:
        bundle = await fetch_own_dating_profile(transaction, user.id)
        if bundle is None:
            return None
        base, photos, prompts = bundle
        return dating_profile_to_own(base, photos, prompts)


profiles_router = Router(
    path="",
    route_handlers=[ProfilesController, DatingProfilesController],
    tags=["profiles"],
    guards=[requires_session],
)
