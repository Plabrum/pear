from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate
from app.domain.prompts.schemas import (
    AuthoredPromptResponse,
    AuthoredResponseStatus,
    ProfilePrompt as ProfilePromptSchema,
    PromptResponse as PromptResponseSchema,
    PromptResponseAuthor,
    PromptTemplate as PromptTemplateSchema,
)

if TYPE_CHECKING:
    from app.domain.prompts.queries import AuthoredResponseRow

# `url_by_media` maps a Media id -> its resolved URL; the route batches one
# MediaService resolve over every response-author avatar, then hands it down.
UrlByMedia = dict[UUID, str]


def _iso(value: datetime | date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def _resolve(media_id: UUID | None, url_by_media: UrlByMedia) -> str | None:
    return url_by_media.get(media_id) if media_id is not None else None


def row_to_prompt_template(row: PromptTemplate) -> PromptTemplateSchema:
    return PromptTemplateSchema(id=row.id, question=row.question)


def row_to_prompt_response(
    response: PromptResponse, author: Profile | None, url_by_media: UrlByMedia
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
                avatarUrl=_resolve(author.avatar_media_id, url_by_media),
            )
            if author is not None
            else None
        ),
    )


# A loaded prompt bundle: the prompt, its joined template question, and its
# response thread as (PromptResponse, author Profile | None) pairs.
ResponseBundle = list[tuple[PromptResponse, Profile | None]]


def prompt_bundle_media_ids(bundles: list[tuple[ProfilePrompt, str, ResponseBundle]]) -> list[UUID]:
    """Every author-avatar Media id referenced across a list of prompt bundles."""
    return [
        author.avatar_media_id
        for _, _, responses in bundles
        for _, author in responses
        if author and author.avatar_media_id
    ]


def row_to_profile_prompt(
    prompt: ProfilePrompt,
    question: str,
    responses: ResponseBundle,
    url_by_media: UrlByMedia,
) -> ProfilePromptSchema:
    return ProfilePromptSchema(
        id=prompt.id,
        datingProfileId=prompt.dating_profile_id,
        answer=prompt.answer,
        createdAt=_iso(prompt.created_at),
        template=PromptTemplateSchema(id=prompt.prompt_template_id, question=question),
        responses=[row_to_prompt_response(r, author, url_by_media) for r, author in responses],
    )


def _authored_status(row: AuthoredResponseRow) -> AuthoredResponseStatus:
    if row.is_rejected:
        return "not_accepted"
    if row.is_approved:
        return "accepted"
    return "pending"


def authored_response_to_dto(row: AuthoredResponseRow) -> AuthoredPromptResponse:
    """Map a response the caller authored to its wire DTO with a folded status."""
    return AuthoredPromptResponse(
        id=row.id,
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        promptQuestion=row.prompt_question,
        message=row.message,
        status=_authored_status(row),
        createdAt=row.created_at.isoformat() if row.created_at is not None else "",
    )
