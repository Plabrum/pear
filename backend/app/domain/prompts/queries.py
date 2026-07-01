"""SQLAlchemy reads for the prompts domain.

Ported from `supabase/functions/api/domains/prompts/queries.ts`. Join-heavy reads
(profile prompts + their template + the response thread with each response's
author) and a handful of relationship predicates the create-response action needs
(prompt owner lookup, active-wingperson check, matched-with check) — exactly the
case the recipe carves out for a `queries.py` (`db: AsyncSession` first arg, no
Litestar/msgspec imports). RLS enforces *access*; these `where` clauses are for
correctness/relevance only.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import asc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.models import DatingProfile
from app.domain.matches.models import Match
from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate
from app.domain.prompts.transformers import ResponseBundle

# ── Templates ──────────────────────────────────────────────────────────────────


async def fetch_prompt_templates(db: AsyncSession) -> list[PromptTemplate]:
    """All templates, ordered by question (matches the Hono `orderBy(asc(question))`)."""
    rows = (await db.execute(select(PromptTemplate).order_by(asc(PromptTemplate.question)))).scalars().all()
    return list(rows)


async def fetch_onboarding_prompt_templates(db: AsyncSession, count: int) -> list[PromptTemplate]:
    """A random selection of `count` templates (Hono `orderBy(random()) limit(count)`)."""
    rows = (await db.execute(select(PromptTemplate).order_by(func.random()).limit(count))).scalars().all()
    return list(rows)


# ── Profile prompts ────────────────────────────────────────────────────────────


async def fetch_own_dating_profile_id(db: AsyncSession, user_id: UUID) -> UUID | None:
    return (
        await db.execute(select(DatingProfile.id).where(DatingProfile.user_id == user_id).limit(1))
    ).scalar_one_or_none()


async def _fetch_prompt_responses(db: AsyncSession, prompt_ids: list[UUID]) -> dict[UUID, ResponseBundle]:
    """Response threads (each with its author) grouped by profile_prompt_id."""
    if not prompt_ids:
        return {}
    author = aliased(Profile)
    rows = (
        await db.execute(
            select(PromptResponse, author)
            .outerjoin(author, author.id == PromptResponse.user_id)
            .where(PromptResponse.profile_prompt_id.in_(prompt_ids))
            .order_by(asc(PromptResponse.created_at))
        )
    ).all()
    by_prompt: dict[UUID, ResponseBundle] = {}
    for response, author_obj in rows:
        by_prompt.setdefault(response.profile_prompt_id, []).append((response, author_obj))
    return by_prompt


async def fetch_own_profile_prompts(db: AsyncSession, user_id: UUID) -> list[tuple[ProfilePrompt, str, ResponseBundle]]:
    """The caller's profile prompts with their template question + response threads."""
    prompt_rows = (
        await db.execute(
            select(ProfilePrompt, PromptTemplate.question)
            .join(DatingProfile, DatingProfile.id == ProfilePrompt.dating_profile_id)
            .join(PromptTemplate, PromptTemplate.id == ProfilePrompt.prompt_template_id)
            .where(DatingProfile.user_id == user_id)
            .order_by(asc(ProfilePrompt.created_at))
        )
    ).all()
    if not prompt_rows:
        return []

    by_prompt = await _fetch_prompt_responses(db, [p.id for p, _ in prompt_rows])
    return [(prompt, question, by_prompt.get(prompt.id, [])) for prompt, question in prompt_rows]


async def fetch_profile_prompt_with_question(
    db: AsyncSession, profile_prompt_id: UUID
) -> tuple[ProfilePrompt, str, ResponseBundle] | None:
    """A single profile prompt (used to render a freshly-created prompt)."""
    row = (
        await db.execute(
            select(ProfilePrompt, PromptTemplate.question)
            .join(PromptTemplate, PromptTemplate.id == ProfilePrompt.prompt_template_id)
            .where(ProfilePrompt.id == profile_prompt_id)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    prompt, question = row
    by_prompt = await _fetch_prompt_responses(db, [prompt.id])
    return prompt, question, by_prompt.get(prompt.id, [])


# ── Prompt responses ─────────────────────────────────────────────────────────


async def fetch_profile_prompt_owner(db: AsyncSession, profile_prompt_id: UUID) -> UUID | None:
    """The user_id of the dater who owns the dating profile this prompt belongs to."""
    return (
        await db.execute(
            select(DatingProfile.user_id)
            .join(ProfilePrompt, ProfilePrompt.dating_profile_id == DatingProfile.id)
            .where(ProfilePrompt.id == profile_prompt_id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def is_active_wingperson(db: AsyncSession, dater_id: UUID, winger_id: UUID) -> bool:
    """Whether `winger_id` is an active wingperson of `dater_id`."""
    row = (
        await db.execute(
            select(Contact.id)
            .where(
                Contact.user_id == dater_id,
                Contact.winger_id == winger_id,
                Contact.wingperson_status == WingpersonStatus.ACTIVE,
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def is_matched_with(db: AsyncSession, viewer_id: UUID, other_user_id: UUID) -> bool:
    """Whether `viewer_id` and `other_user_id` have a mutual match (either ordering)."""
    row = (
        await db.execute(
            select(Match.id)
            .where(
                or_(
                    (Match.user_a_id == viewer_id) & (Match.user_b_id == other_user_id),
                    (Match.user_a_id == other_user_id) & (Match.user_b_id == viewer_id),
                )
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def fetch_prompt_response_author(db: AsyncSession, response: PromptResponse) -> Profile | None:
    """The author profile of a response (the Hono LEFT JOIN onto profiles)."""
    return (await db.execute(select(Profile).where(Profile.id == response.user_id).limit(1))).scalar_one_or_none()


async def is_response_profile_owner(db: AsyncSession, response: PromptResponse, owner_id: UUID) -> bool:
    """Whether `owner_id` owns the dating profile the response's prompt belongs to."""
    row = (
        await db.execute(
            select(DatingProfile.id)
            .join(ProfilePrompt, ProfilePrompt.dating_profile_id == DatingProfile.id)
            .where(
                ProfilePrompt.id == response.profile_prompt_id,
                DatingProfile.user_id == owner_id,
            )
            .limit(1)
        )
    ).first()
    return row is not None
