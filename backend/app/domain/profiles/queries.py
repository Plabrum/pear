from __future__ import annotations

from uuid import UUID

from sqlalchemy import asc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.dating_profiles.models import DatingProfile
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.domain.profiles.transformers import PhotoBundle, PromptBundle, ResponseBundle
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate


async def fetch_profile(db: AsyncSession, user_id: UUID) -> Profile | None:
    return (await db.execute(select(Profile).where(Profile.id == user_id).limit(1))).scalar_one_or_none()


async def fetch_dating_profile_base(db: AsyncSession, user_id: UUID) -> DatingProfile | None:
    return (
        await db.execute(select(DatingProfile).where(DatingProfile.user_id == user_id).limit(1))
    ).scalar_one_or_none()


async def _fetch_photos(db: AsyncSession, dating_profile_id: UUID, *, approved_only: bool = False) -> PhotoBundle:
    suggester = aliased(Profile)
    stmt = (
        select(ProfilePhoto, suggester.chosen_name)
        .outerjoin(suggester, suggester.id == ProfilePhoto.suggester_id)
        .where(ProfilePhoto.dating_profile_id == dating_profile_id)
        .order_by(asc(ProfilePhoto.display_order))
    )
    if approved_only:
        # Storage-RLS "approved-public read" intent: a PUBLIC viewer only ever sees
        # (and gets a presigned URL for) approved photos. The owner's own view
        # (approved_only=False) still shows pending photos in the editor.
        stmt = stmt.where(ProfilePhoto.approved_at.is_not(None))
    rows = (await db.execute(stmt)).all()
    return [(photo, name) for photo, name in rows]


async def _fetch_prompts(db: AsyncSession, dating_profile_id: UUID) -> PromptBundle:
    prompt_rows = (
        await db.execute(
            select(ProfilePrompt, PromptTemplate.question)
            .join(PromptTemplate, PromptTemplate.id == ProfilePrompt.prompt_template_id)
            .where(ProfilePrompt.dating_profile_id == dating_profile_id)
            .order_by(asc(ProfilePrompt.created_at))
        )
    ).all()
    if not prompt_rows:
        return []

    prompt_ids = [p.id for p, _ in prompt_rows]
    author = aliased(Profile)
    response_rows = (
        await db.execute(
            select(PromptResponse, author)
            .outerjoin(author, author.id == PromptResponse.user_id)
            .where(PromptResponse.profile_prompt_id.in_(prompt_ids))
            .order_by(asc(PromptResponse.created_at))
        )
    ).all()

    by_prompt: dict[UUID, ResponseBundle] = {}
    for response, author_obj in response_rows:
        by_prompt.setdefault(response.profile_prompt_id, []).append((response, author_obj))

    return [(prompt, question, by_prompt.get(prompt.id, [])) for prompt, question in prompt_rows]


async def fetch_own_dating_profile(
    db: AsyncSession, user_id: UUID
) -> tuple[DatingProfile, PhotoBundle, PromptBundle] | None:
    base = await fetch_dating_profile_base(db, user_id)
    if base is None:
        return None
    photos = await _fetch_photos(db, base.id)
    prompts = await _fetch_prompts(db, base.id)
    return base, photos, prompts


async def fetch_public_profile(
    db: AsyncSession, user_id: UUID
) -> tuple[Profile, DatingProfile | None, PhotoBundle, PromptBundle] | None:
    profile = await fetch_profile(db, user_id)
    if profile is None:
        return None
    base = await fetch_dating_profile_base(db, user_id)
    if base is None:
        return profile, None, [], []
    # Public viewers only see approved photos (approved-public read intent).
    photos = await _fetch_photos(db, base.id, approved_only=True)
    prompts = await _fetch_prompts(db, base.id)
    return profile, base, photos, prompts
