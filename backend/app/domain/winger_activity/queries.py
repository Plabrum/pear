"""SQLAlchemy reads for the winger-activity domain.

Ported from `supabase/functions/api/domains/winger-activity/queries.ts`. First arg
is always `db: AsyncSession`; no Litestar/msgspec imports. These are join-heavy
reads of the suggestions/photos/prompt-responses the caller (a winger) authored,
folded with their outcomes — exactly the case the recipe carves a `queries.py` out
for. RLS enforces *access*; the explicit `where` clauses are for correctness/
relevance (suggester/author scoping + ordering).

TODO(events): the migration doc (docs/migration/05-domains.md) suggests building
this feed off the Phase-2 events layer (winger actions emit events; the dater's
feed reads them) instead of re-querying the decisions/profile_photos/
prompt_responses tables. This is a faithful 1:1 port of the Hono SQL; the
events-based rewrite is deferred.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, desc, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate


@dataclass
class SuggestionRow:
    id: UUID
    decision: DecisionType | None
    has_match: bool
    dater_id: UUID
    dater_name: str | None
    recipient_name: str | None
    created_at: datetime | None


@dataclass
class PhotoRow:
    id: UUID
    dater_id: UUID
    dater_name: str | None
    storage_url: str
    approved_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime | None


@dataclass
class PromptRow:
    id: UUID
    dater_id: UUID
    dater_name: str | None
    prompt_question: str
    message: str
    is_approved: bool
    is_rejected: bool
    created_at: datetime | None


async def fetch_people_activity(db: AsyncSession, winger_id: UUID, limit: int) -> list[SuggestionRow]:
    """Cards the winger suggested + whether each became a match, newest first.

    Mirrors the Hono aggregate: every decision row the winger authored
    (`suggested_by = winger_id`), joined to the dater (actor) and recipient profile
    names, with a correlated EXISTS that reports whether a match now joins the
    actor and recipient (in either id ordering).
    """
    dater = aliased(Profile)
    recipient = aliased(Profile)

    match_exists_expr = exists(
        select(Match.id).where(
            or_(
                and_(
                    Match.user_a_id == Decision.actor_id,
                    Match.user_b_id == Decision.recipient_id,
                ),
                and_(
                    Match.user_a_id == Decision.recipient_id,
                    Match.user_b_id == Decision.actor_id,
                ),
            )
        )
    )

    rows = (
        await db.execute(
            select(
                Decision.id,
                Decision.decision,
                match_exists_expr,
                Decision.actor_id,
                dater.chosen_name,
                recipient.chosen_name,
                Decision.created_at,
            )
            .join(dater, dater.id == Decision.actor_id)
            .join(recipient, recipient.id == Decision.recipient_id)
            .where(
                and_(
                    Decision.suggested_by.is_not(None),
                    Decision.suggested_by == winger_id,
                )
            )
            .order_by(desc(Decision.created_at))
            .limit(limit)
        )
    ).all()

    return [
        SuggestionRow(
            id=decision_id,
            decision=decision,
            has_match=bool(has_match),
            dater_id=dater_id,
            dater_name=dater_name,
            recipient_name=recipient_name,
            created_at=created_at,
        )
        for (
            decision_id,
            decision,
            has_match,
            dater_id,
            dater_name,
            recipient_name,
            created_at,
        ) in rows
    ]


async def fetch_photos_activity(db: AsyncSession, winger_id: UUID, limit: int) -> list[PhotoRow]:
    """Photos the winger suggested + their approval status, newest first."""
    rows = (
        await db.execute(
            select(
                ProfilePhoto.id,
                DatingProfile.user_id,
                Profile.chosen_name,
                ProfilePhoto.storage_url,
                ProfilePhoto.approved_at,
                ProfilePhoto.rejected_at,
                ProfilePhoto.created_at,
            )
            .join(DatingProfile, DatingProfile.id == ProfilePhoto.dating_profile_id)
            .join(Profile, Profile.id == DatingProfile.user_id)
            .where(ProfilePhoto.suggester_id == winger_id)
            .order_by(desc(ProfilePhoto.created_at))
            .limit(limit)
        )
    ).all()

    return [
        PhotoRow(
            id=photo_id,
            dater_id=dater_id,
            dater_name=dater_name,
            storage_url=storage_url,
            approved_at=approved_at,
            rejected_at=rejected_at,
            created_at=created_at,
        )
        for (
            photo_id,
            dater_id,
            dater_name,
            storage_url,
            approved_at,
            rejected_at,
            created_at,
        ) in rows
    ]


async def fetch_prompts_activity(db: AsyncSession, winger_id: UUID, limit: int) -> list[PromptRow]:
    """Prompt responses the winger authored + their acceptance status, newest first.

    Scoped by `prompt_responses.user_id = winger_id` (the author), mirroring the
    Hono query — note this differs from the photo feed's `suggester_id` scoping.
    """
    rows = (
        await db.execute(
            select(
                PromptResponse.id,
                DatingProfile.user_id,
                Profile.chosen_name,
                PromptTemplate.question,
                PromptResponse.message,
                PromptResponse.is_approved,
                PromptResponse.is_rejected,
                PromptResponse.created_at,
            )
            .join(ProfilePrompt, ProfilePrompt.id == PromptResponse.profile_prompt_id)
            .join(PromptTemplate, PromptTemplate.id == ProfilePrompt.prompt_template_id)
            .join(DatingProfile, DatingProfile.id == ProfilePrompt.dating_profile_id)
            .join(Profile, Profile.id == DatingProfile.user_id)
            .where(PromptResponse.user_id == winger_id)
            .order_by(desc(PromptResponse.created_at))
            .limit(limit)
        )
    ).all()

    return [
        PromptRow(
            id=response_id,
            dater_id=dater_id,
            dater_name=dater_name,
            prompt_question=prompt_question,
            message=message,
            is_approved=is_approved,
            is_rejected=is_rejected,
            created_at=created_at,
        )
        for (
            response_id,
            dater_id,
            dater_name,
            prompt_question,
            message,
            is_approved,
            is_rejected,
            created_at,
        ) in rows
    ]
