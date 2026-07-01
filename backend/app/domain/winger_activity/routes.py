"""Read endpoints for the winger-activity domain (READS ONLY).

Ported from `supabase/functions/api/domains/winger-activity/route.ts`:
  * GET /winger-activity/people  -> cards the winger suggested + match outcomes
  * GET /winger-activity/photos  -> photos the winger suggested + approval status
  * GET /winger-activity/prompts -> prompt responses the winger authored + status

Each is a limit-bounded feed of the caller's own contributions folded with their
outcomes — custom-shaped aggregates, not list/detail-by-id resources — so they are
explicit `@get` handlers on a `Controller` taking the injected RLS-scoped
`transaction` and authenticated `user` rather than the declarative
`make_crud_controller`. There is no `actions.py`: this domain is read-only.

`operation_id`s (`getApiWingerActivityPeople` / `...Photos` / `...Prompts`) keep the
Orval hook names stable across the Hono -> Litestar cutover. The `limit` query param
mirrors the Hono Zod (`int, 1..100, default 50`).
"""

from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.winger_activity.queries import (
    fetch_people_activity,
    fetch_photos_activity,
    fetch_prompts_activity,
)
from app.domain.winger_activity.schemas import (
    PeopleActivityRow,
    PhotoActivityRow,
    PromptActivityRow,
)
from app.domain.winger_activity.transformers import (
    transform_photo,
    transform_prompt,
    transform_suggestion,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


class WingerActivityController(Controller):
    """GET /winger-activity/{people,photos,prompts}."""

    path = "/winger-activity"

    @get("/people", operation_id="getApiWingerActivityPeople")
    async def get_people(
        self,
        user: User,
        transaction: AsyncSession,
        limit: int = Parameter(query="limit", default=50, ge=1, le=100),
    ) -> list[PeopleActivityRow]:
        rows = await fetch_people_activity(transaction, user.id, limit)
        return [transform_suggestion(r) for r in rows]

    @get("/photos", operation_id="getApiWingerActivityPhotos")
    async def get_photos(
        self,
        user: User,
        transaction: AsyncSession,
        limit: int = Parameter(query="limit", default=50, ge=1, le=100),
    ) -> list[PhotoActivityRow]:
        rows = await fetch_photos_activity(transaction, user.id, limit)
        return [transform_photo(r) for r in rows]

    @get("/prompts", operation_id="getApiWingerActivityPrompts")
    async def get_prompts(
        self,
        user: User,
        transaction: AsyncSession,
        limit: int = Parameter(query="limit", default=50, ge=1, le=100),
    ) -> list[PromptActivityRow]:
        rows = await fetch_prompts_activity(transaction, user.id, limit)
        return [transform_prompt(r) for r in rows]


winger_activity_router = Router(
    path="",
    route_handlers=[WingerActivityController],
    tags=["winger-activity"],
    guards=[requires_session],
)
