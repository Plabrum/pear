from __future__ import annotations

from uuid import UUID

from sqlalchemy import Integer, and_, asc, case, desc, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.matches.transformers import MatchPromptRow, MatchRow, WingNoteRow
from app.domain.messages.models import Message
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptTemplate


async def fetch_matches(db: AsyncSession, viewer_id: UUID) -> list[MatchRow]:
    """All matches for the viewer, newest first, with the other user's summary.

    The aggregate folds in the other profile + their dating profile (city/bio/
    interests), a year-based age from date_of_birth, the first approved photo, and
    whether any messages exist in the match.
    """
    other_id_expr = case(
        (Match.user_a_id == viewer_id, Match.user_b_id),
        else_=Match.user_a_id,
    )
    age_expr = case(
        (Profile.date_of_birth.is_(None), None),
        else_=func.extract("year", func.age(Profile.date_of_birth)).cast(Integer),
    )
    first_photo_expr = (
        select(ProfilePhoto.storage_url)
        .where(
            and_(
                ProfilePhoto.dating_profile_id == DatingProfile.id,
                ProfilePhoto.approved_at.is_not(None),
            )
        )
        .order_by(asc(ProfilePhoto.display_order))
        .limit(1)
        .correlate(DatingProfile)
        .scalar_subquery()
    )
    has_messages_expr = exists(select(Message.id).where(Message.match_id == Match.id))

    rows = (
        await db.execute(
            select(
                Match.id,
                Match.created_at,
                has_messages_expr,
                other_id_expr,
                Profile.chosen_name,
                Profile.date_of_birth,
                age_expr,
                DatingProfile.city,
                DatingProfile.bio,
                DatingProfile.interests,
                first_photo_expr,
            )
            .outerjoin(Profile, Profile.id == other_id_expr)
            .outerjoin(DatingProfile, DatingProfile.user_id == Profile.id)
            .where(or_(Match.user_a_id == viewer_id, Match.user_b_id == viewer_id))
            .order_by(desc(Match.created_at))
        )
    ).all()

    return [
        MatchRow(
            match_id=match_id,
            created_at=created_at,
            has_messages=bool(has_messages),
            other_user_id=other_user_id,
            chosen_name=chosen_name,
            date_of_birth=date_of_birth,
            age=int(age) if age is not None else None,
            city=city,
            bio=bio,
            interests=interests,
            first_photo=first_photo,
        )
        for (
            match_id,
            created_at,
            has_messages,
            other_user_id,
            chosen_name,
            date_of_birth,
            age,
            city,
            bio,
            interests,
            first_photo,
        ) in rows
    ]


async def fetch_match_other_user_id(db: AsyncSession, viewer_id: UUID, match_id: UUID) -> UUID | None:
    """The other participant's id for a match the viewer is party to, else None.

    RLS already hides non-participant matches, but the explicit participant `where`
    keeps the contract obvious and returns None (-> 404) when the viewer isn't in it.
    """
    other_id_expr = case(
        (Match.user_a_id == viewer_id, Match.user_b_id),
        else_=Match.user_a_id,
    )
    row = (
        await db.execute(
            select(other_id_expr)
            .where(
                and_(
                    Match.id == match_id,
                    or_(Match.user_a_id == viewer_id, Match.user_b_id == viewer_id),
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


async def fetch_wing_note_for_match(db: AsyncSession, viewer_id: UUID, other_user_id: UUID) -> WingNoteRow | None:
    """The wingperson note attached to the viewer's decision on the other user.

    The decision row where the viewer is the actor, the other user the recipient,
    and a note is present — joined to the suggesting winger's profile name.
    """
    winger = aliased(Profile)
    row = (
        await db.execute(
            select(
                Decision.note,
                Decision.suggested_by,
                winger.id,
                winger.chosen_name,
            )
            .outerjoin(winger, winger.id == Decision.suggested_by)
            .where(
                and_(
                    Decision.actor_id == viewer_id,
                    Decision.recipient_id == other_user_id,
                    Decision.note.is_not(None),
                )
            )
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    note, suggested_by, winger_id, winger_chosen_name = row
    return WingNoteRow(
        note=note,
        suggested_by=suggested_by,
        winger_id=winger_id,
        winger_chosen_name=winger_chosen_name,
    )


async def fetch_prompts_for_user(db: AsyncSession, user_id: UUID) -> list[MatchPromptRow]:
    """The other user's profile prompts (answer + template question), oldest first."""
    rows = (
        await db.execute(
            select(
                ProfilePrompt.id,
                ProfilePrompt.answer,
                PromptTemplate.id,
                PromptTemplate.question,
            )
            .join(DatingProfile, DatingProfile.id == ProfilePrompt.dating_profile_id)
            .outerjoin(PromptTemplate, PromptTemplate.id == ProfilePrompt.prompt_template_id)
            .where(DatingProfile.user_id == user_id)
            .order_by(asc(ProfilePrompt.created_at))
        )
    ).all()
    return [
        MatchPromptRow(
            id=prompt_id,
            answer=answer,
            template_id=template_id,
            template_question=template_question,
        )
        for (prompt_id, answer, template_id, template_question) in rows
    ]
