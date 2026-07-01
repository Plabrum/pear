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
from app.platform.media.client import BaseMediaClient

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
    async def own_prompts(self, user: User, transaction: AsyncSession, media: BaseMediaClient) -> list[ProfilePrompt]:
        bundles = await fetch_own_profile_prompts(transaction, user.id)
        return [row_to_profile_prompt(prompt, question, responses, media) for prompt, question, responses in bundles]


prompts_router = Router(
    path="",
    route_handlers=[PromptTemplatesController, ProfilePromptsController],
    tags=["prompts"],
    guards=[requires_session],
)
