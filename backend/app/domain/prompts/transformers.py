from __future__ import annotations

from datetime import date, datetime

from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate
from app.domain.prompts.schemas import (
    ProfilePrompt as ProfilePromptSchema,
    PromptResponse as PromptResponseSchema,
    PromptResponseAuthor,
    PromptTemplate as PromptTemplateSchema,
)
from app.platform.media.client import BaseMediaClient


def _iso(value: datetime | date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _avatar_url(key: str | None, media: BaseMediaClient) -> str | None:
    """Avatar keys resolve to a public-read URL (no presign needed)."""
    return media.public_url(key) if key else None


def row_to_prompt_template(row: PromptTemplate) -> PromptTemplateSchema:
    return PromptTemplateSchema(id=row.id, question=row.question)


def row_to_prompt_response(
    response: PromptResponse, author: Profile | None, media: BaseMediaClient
) -> PromptResponseSchema:
    return PromptResponseSchema(
        id=response.id,
        profilePromptId=response.profile_prompt_id,
        message=response.message,
        isApproved=response.is_approved,
        userId=response.user_id,
        createdAt=_iso(response.created_at),
        author=(
            PromptResponseAuthor(
                id=author.id,
                chosenName=author.chosen_name,
                avatarUrl=_avatar_url(author.avatar_url, media),
            )
            if author is not None
            else None
        ),
    )


# A loaded prompt bundle: the prompt, its joined template question, and its
# response thread as (PromptResponse, author Profile | None) pairs.
ResponseBundle = list[tuple[PromptResponse, Profile | None]]


def row_to_profile_prompt(
    prompt: ProfilePrompt,
    question: str,
    responses: ResponseBundle,
    media: BaseMediaClient,
) -> ProfilePromptSchema:
    return ProfilePromptSchema(
        id=prompt.id,
        datingProfileId=prompt.dating_profile_id,
        answer=prompt.answer,
        createdAt=_iso(prompt.created_at),
        template=PromptTemplateSchema(id=prompt.prompt_template_id, question=question),
        responses=[row_to_prompt_response(r, author, media) for r, author in responses],
    )
