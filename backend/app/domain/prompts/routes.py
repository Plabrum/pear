from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.prompts.queries import (
    fetch_authored_prompt_responses,
    fetch_onboarding_prompt_templates,
    fetch_own_profile_prompts,
    fetch_prompt_templates,
)
from app.domain.prompts.schemas import (
    AuthoredPromptResponsesResponse,
    ProfilePrompt,
    PromptTemplate,
)
from app.domain.prompts.transformers import (
    authored_response_to_dto,
    prompt_bundle_media_ids,
    row_to_profile_prompt,
    row_to_prompt_template,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.service import MediaService

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
    async def own_prompts(
        self, user: User, transaction: AsyncSession, media_service: MediaService
    ) -> list[ProfilePrompt]:
        bundles = await fetch_own_profile_prompts(transaction, user.id)
        url_by_media = await media_service.resolve_urls(prompt_bundle_media_ids(bundles))
        return [
            row_to_profile_prompt(prompt, question, responses, url_by_media) for prompt, question, responses in bundles
        ]


class PromptResponsesController(Controller):
    """GET /prompt-responses/me — responses the caller authored."""

    path = "/prompt-responses"

    @get("/me", operation_id="getApiPromptResponsesMe")
    async def authored_responses(
        self,
        user: User,
        transaction: AsyncSession,
        limit: int = Parameter(query="limit", default=50, ge=1, le=100),
    ) -> AuthoredPromptResponsesResponse:
        """The responses the caller wrote on daters' prompts (`user_id = me`), newest first."""
        rows = await fetch_authored_prompt_responses(transaction, user.id, limit)
        return [authored_response_to_dto(row) for row in rows]


prompts_router = Router(
    path="",
    route_handlers=[PromptTemplatesController, ProfilePromptsController, PromptResponsesController],
    tags=["prompts"],
    guards=[requires_session],
)
