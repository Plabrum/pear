from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import asc, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.queries import is_active_wingperson  # noqa: F401  (re-exported)
from app.domain.dating_profiles.models import DatingProfile
from app.domain.matches.models import Match
from app.domain.profiles.models import Profile
from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate
from app.domain.prompts.transformers import ResponseBundle
from app.utils.sqids import Sqid

# ── Templates ──────────────────────────────────────────────────────────────────


async def fetch_prompt_templates(db: AsyncSession) -> list[PromptTemplate]:
    """All templates, ordered by question."""
    rows = (await db.execute(select(PromptTemplate).order_by(asc(PromptTemplate.question)))).scalars().all()
    return list(rows)


async def fetch_onboarding_prompt_templates(db: AsyncSession, count: int) -> list[PromptTemplate]:
    """A random selection of `count` templates."""
    rows = (await db.execute(select(PromptTemplate).order_by(func.random()).limit(count))).scalars().all()
    return list(rows)


# ── Profile prompts ────────────────────────────────────────────────────────────


async def fetch_own_dating_profile_id(db: AsyncSession, user_id: Sqid) -> Sqid | None:
    return (
        await db.execute(select(DatingProfile.id).where(DatingProfile.user_id == user_id).limit(1))
    ).scalar_one_or_none()


async def _fetch_prompt_responses(db: AsyncSession, prompt_ids: list[Sqid]) -> dict[Sqid, ResponseBundle]:
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
    by_prompt: dict[Sqid, ResponseBundle] = {}
    for response, author_obj in rows:
        by_prompt.setdefault(response.profile_prompt_id, []).append((response, author_obj))
    return by_prompt


async def fetch_own_profile_prompts(db: AsyncSession, user_id: Sqid) -> list[tuple[ProfilePrompt, str, ResponseBundle]]:
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


# ── Prompt responses ─────────────────────────────────────────────────────────


@dataclass
class AuthoredResponseRow:
    """A response the caller authored, with the prompt's question + owning dater."""

    id: Sqid
    dater_id: Sqid
    dater_name: str | None
    prompt_question: str
    message: str
    state: ApprovalState
    created_at: datetime | None


async def fetch_authored_prompt_responses(db: AsyncSession, author_id: Sqid, limit: int) -> list[AuthoredResponseRow]:
    """Responses the caller authored (`user_id = me`) + their acceptance status, newest first.

    Joins each response's prompt to its template (the question) and to the owning
    dater's profile (the dater's name).
    """
    rows = (
        await db.execute(
            select(
                PromptResponse.id,
                DatingProfile.user_id,
                Profile.chosen_name,
                PromptTemplate.question,
                PromptResponse.message,
                PromptResponse.state,
                PromptResponse.created_at,
            )
            .join(ProfilePrompt, ProfilePrompt.id == PromptResponse.profile_prompt_id)
            .join(PromptTemplate, PromptTemplate.id == ProfilePrompt.prompt_template_id)
            .join(DatingProfile, DatingProfile.id == ProfilePrompt.dating_profile_id)
            .join(Profile, Profile.id == DatingProfile.user_id)
            .where(PromptResponse.user_id == author_id)
            .order_by(desc(PromptResponse.created_at))
            .limit(limit)
        )
    ).all()

    return [
        AuthoredResponseRow(
            id=response_id,
            dater_id=dater_id,
            dater_name=dater_name,
            prompt_question=prompt_question,
            message=message,
            state=state,
            created_at=created_at,
        )
        for (
            response_id,
            dater_id,
            dater_name,
            prompt_question,
            message,
            state,
            created_at,
        ) in rows
    ]


async def fetch_profile_prompt_owner(db: AsyncSession, profile_prompt_id: Sqid) -> Sqid | None:
    """The user_id of the dater who owns the dating profile this prompt belongs to."""
    return (
        await db.execute(
            select(DatingProfile.user_id)
            .join(ProfilePrompt, ProfilePrompt.dating_profile_id == DatingProfile.id)
            .where(ProfilePrompt.id == profile_prompt_id)
            .limit(1)
        )
    ).scalar_one_or_none()


async def is_matched_with(db: AsyncSession, viewer_id: Sqid, other_user_id: Sqid) -> bool:
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
