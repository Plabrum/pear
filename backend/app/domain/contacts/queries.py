from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.contacts.transformers import (
    IncomingInvitationRow,
    SentInvitationRow,
    WingingForDaterRow,
    WingingForTabRow,
    WingpersonRow,
)
from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.models import Decision
from app.domain.profiles.models import Profile
from app.platform.media.queries import public_key_expr


async def fetch_push_token(db: AsyncSession, user_id: UUID) -> str | None:
    return (await db.execute(select(Profile.push_token).where(Profile.id == user_id).limit(1))).scalar_one_or_none()


async def fetch_active_wingpeople(db: AsyncSession, dater_id: UUID) -> list[WingpersonRow]:
    winger = aliased(Profile)
    rows = (
        await db.execute(
            select(
                Contact.id,
                Contact.created_at,
                Contact.winger_id,
                winger.chosen_name,
                winger.gender,
                public_key_expr(winger.avatar_media_id).label("winger_avatar_url"),
            )
            .outerjoin(winger, winger.id == Contact.winger_id)
            .where(
                and_(
                    Contact.user_id == dater_id,
                    Contact.wingperson_status == WingpersonStatus.ACTIVE,
                )
            )
            .order_by(asc(Contact.created_at))
        )
    ).all()
    return [
        WingpersonRow(
            id=cid,
            created_at=created_at,
            winger_id=winger_id,
            winger_chosen_name=name,
            winger_gender=gender,
            winger_avatar_url=avatar,
        )
        for cid, created_at, winger_id, name, gender, avatar in rows
    ]


async def fetch_incoming_invitations(db: AsyncSession, winger_id: UUID) -> list[IncomingInvitationRow]:
    dater = aliased(Profile)
    rows = (
        await db.execute(
            select(
                Contact.id,
                Contact.created_at,
                Contact.user_id,
                dater.chosen_name,
            )
            .outerjoin(dater, dater.id == Contact.user_id)
            .where(
                and_(
                    Contact.winger_id == winger_id,
                    Contact.wingperson_status == WingpersonStatus.INVITED,
                )
            )
            .order_by(desc(Contact.created_at))
        )
    ).all()
    return [
        IncomingInvitationRow(id=cid, created_at=created_at, dater_id=dater_id, dater_chosen_name=name)
        for cid, created_at, dater_id, name in rows
    ]


async def fetch_sent_invitations(db: AsyncSession, dater_id: UUID) -> list[SentInvitationRow]:
    winger = aliased(Profile)
    rows = (
        await db.execute(
            select(
                Contact.id,
                Contact.created_at,
                Contact.phone_number,
                Contact.winger_id,
                winger.chosen_name,
            )
            .outerjoin(winger, winger.id == Contact.winger_id)
            .where(
                and_(
                    Contact.user_id == dater_id,
                    Contact.wingperson_status == WingpersonStatus.INVITED,
                )
            )
            .order_by(desc(Contact.created_at))
        )
    ).all()
    return [
        SentInvitationRow(
            id=cid,
            created_at=created_at,
            phone_number=phone,
            winger_id=winger_id,
            winger_chosen_name=name,
        )
        for cid, created_at, phone, winger_id, name in rows
    ]


async def fetch_winging_for(db: AsyncSession, winger_id: UUID) -> list[WingingForDaterRow]:
    dater = aliased(Profile)
    rows = (
        await db.execute(
            select(
                Contact.id,
                Contact.created_at,
                Contact.user_id,
                dater.chosen_name,
                public_key_expr(dater.avatar_media_id).label("dater_avatar_url"),
                DatingProfile.interests,
                DatingProfile.bio,
            )
            .outerjoin(dater, dater.id == Contact.user_id)
            .outerjoin(DatingProfile, DatingProfile.user_id == Contact.user_id)
            .where(
                and_(
                    Contact.winger_id == winger_id,
                    Contact.wingperson_status == WingpersonStatus.ACTIVE,
                )
            )
            .order_by(asc(Contact.created_at))
        )
    ).all()
    return [
        WingingForDaterRow(
            id=cid,
            created_at=created_at,
            dater_id=dater_id,
            dater_chosen_name=name,
            dater_avatar_url=avatar,
            dater_interests=list(interests) if interests is not None else None,
            dater_bio=bio,
        )
        for cid, created_at, dater_id, name, avatar, interests, bio in rows
    ]


async def fetch_winging_for_tabs(db: AsyncSession, winger_id: UUID) -> list[WingingForTabRow]:
    """The daters the caller actively wings for — my active winger-side edges, newest first.

    Active `contacts` where the caller is the `winger_id`, joined to each dater's
    profile for the tab's display name. The minimal `{id, name}` projection backs the
    winger-side dater-switcher tabs.
    """
    dater = aliased(Profile)
    rows = (
        await db.execute(
            select(
                Contact.user_id,
                dater.chosen_name,
                Contact.created_at,
            )
            .join(dater, dater.id == Contact.user_id)
            .where(
                and_(
                    Contact.winger_id == winger_id,
                    Contact.wingperson_status == WingpersonStatus.ACTIVE,
                )
            )
            .order_by(desc(Contact.created_at))
        )
    ).all()
    return [
        WingingForTabRow(id=dater_id, chosen_name=chosen_name, created_at=created_at)
        for dater_id, chosen_name, created_at in rows
    ]


async def fetch_weekly_counts(
    db: AsyncSession,
    dater_id: UUID,
    wingpeople: list[WingpersonRow],
) -> dict[str, int]:
    """contactId -> # of suggestions a winger made to this dater in the last 7 days.

    A single query covers all the dater's active wingers at once so the wingpeople
    bundle stays O(1) round-trips.
    """
    winger_ids: list[UUID] = []
    winger_to_contact_id: dict[UUID, str] = {}
    for w in wingpeople:
        if w.winger_id is not None:
            winger_ids.append(w.winger_id)
            winger_to_contact_id[w.winger_id] = str(w.id)

    if not winger_ids:
        return {}

    since = datetime.now(tz=UTC) - timedelta(days=7)
    rows = (
        await db.execute(
            select(Decision.suggested_by).where(
                and_(
                    Decision.actor_id == dater_id,
                    Decision.suggested_by.in_(winger_ids),
                    Decision.created_at >= since,
                )
            )
        )
    ).all()

    counts: dict[str, int] = {}
    for (suggested_by,) in rows:
        if suggested_by is None:
            continue
        contact_id = winger_to_contact_id.get(suggested_by)
        if contact_id is not None:
            counts[contact_id] = counts.get(contact_id, 0) + 1
    return counts


async def find_profile_id_by_phone(db: AsyncSession, phone_number: str) -> UUID | None:
    return (
        await db.execute(select(Profile.id).where(Profile.phone_number == phone_number).limit(1))
    ).scalar_one_or_none()
