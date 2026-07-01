"""snake_case ORM rows -> camelCase msgspec structs.

Ported from `supabase/functions/api/domains/prompts/transformers.ts`. Maps
SQLAlchemy ORM objects onto the msgspec response structs. Datetime columns render
as ISO-8601 strings to match the Postgres `timestamptz` -> JSON contract the
mobile app already consumes.

The query layer hands these functions ORM objects plus the joined author profile
(nullable, like the Hono LEFT JOIN onto `profiles`) and, for prompts, the joined
template question + the response threads.
"""

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


def _iso(value: datetime | date | None) -> str:
    if value is None:
        return ""
    return value.isoformat()


def row_to_prompt_template(row: PromptTemplate) -> PromptTemplateSchema:
    return PromptTemplateSchema(id=row.id, question=row.question)


def row_to_prompt_response(response: PromptResponse, author: Profile | None) -> PromptResponseSchema:
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
                avatarUrl=author.avatar_url,
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
) -> ProfilePromptSchema:
    return ProfilePromptSchema(
        id=prompt.id,
        datingProfileId=prompt.dating_profile_id,
        answer=prompt.answer,
        createdAt=_iso(prompt.created_at),
        template=PromptTemplateSchema(id=prompt.prompt_template_id, question=question),
        responses=[row_to_prompt_response(r, author) for r, author in responses],
    )
