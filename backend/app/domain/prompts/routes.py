"""Read endpoints for the prompts domain (READS ONLY).

Ported from the GET handlers in `supabase/functions/api/domains/prompts/route.ts`.
All mutations live in `actions.py`.

These reads are custom-shaped — a flat template catalog, a random onboarding
selection, and the caller's prompt threads (each prompt with its template + the
nested response thread, where every response carries its author) — so they are
explicit `@get` handlers on a `Controller` rather than the declarative
`make_crud_controller` (which assumes list + detail-by-row-id). Each handler takes
the injected RLS-scoped `transaction` and the authenticated `user`; RLS enforces
access and the transformers map ORM rows -> camelCase structs.

`operation_id`s match the Hono operation names so the Orval/OpenAPI step regenerates
the mobile hooks with near-zero churn.
"""

from __future__ import annotations

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.prompts.queries import (
    fetch_onboarding_prompt_templates,
    fetch_own_profile_prompts,
    fetch_prompt_templates,
)
from app.domain.prompts.schemas import ProfilePrompt, PromptTemplate
from app.domain.prompts.transformers import (
    row_to_profile_prompt,
    row_to_prompt_template,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User

ONBOARDING_PROMPT_COUNT = 5


class PromptTemplatesController(Controller):
    """GET /prompt-templates and GET /prompt-templates/onboarding."""

    path = "/prompt-templates"

    @get("/", operation_id="getApiPromptTemplates")
    async def list_templates(self, user: User, transaction: AsyncSession) -> list[PromptTemplate]:
        rows = await fetch_prompt_templates(transaction)
        return [row_to_prompt_template(r) for r in rows]

    @get("/onboarding", operation_id="getApiPromptTemplatesOnboarding")
    async def onboarding_templates(self, user: User, transaction: AsyncSession) -> list[PromptTemplate]:
        rows = await fetch_onboarding_prompt_templates(transaction, ONBOARDING_PROMPT_COUNT)
        return [row_to_prompt_template(r) for r in rows]


class ProfilePromptsController(Controller):
    """GET /profile-prompts/me."""

    path = "/profile-prompts"

    @get("/me", operation_id="getApiProfilePromptsMe")
    async def own_prompts(self, user: User, transaction: AsyncSession) -> list[ProfilePrompt]:
        bundles = await fetch_own_profile_prompts(transaction, user.id)
        return [row_to_profile_prompt(prompt, question, responses) for prompt, question, responses in bundles]


prompts_router = Router(
    path="",
    route_handlers=[PromptTemplatesController, ProfilePromptsController],
    tags=["prompts"],
    guards=[requires_session],
)
