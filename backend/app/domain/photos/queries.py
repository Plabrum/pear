from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.models import DatingProfile
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.platform.media.queries import servable_key_expr

# A loaded photo plus the suggester's chosen name (None when self-uploaded).
PhotoRow = tuple[ProfilePhoto, str | None]


@dataclass
class SuggestedPhotoRow:
    """A photo the caller suggested for a dater, plus that dater's name + status."""

    id: UUID
    dater_id: UUID
    dater_name: str | None
    storage_url: str
    approved_at: datetime | None
    rejected_at: datetime | None
    created_at: datetime | None


async def fetch_suggested_photos(db: AsyncSession, suggester_id: UUID, limit: int) -> list[SuggestedPhotoRow]:
    """Photos the caller suggested (`suggester_id = me`) + their approval status, newest first.

    Each row joins the photo's dating profile to its owning dater for the dater's
    name; `storage_url` is the photo media's servable S3 key (presigned downstream).
    """
    rows = (
        await db.execute(
            select(
                ProfilePhoto.id,
                DatingProfile.user_id,
                Profile.chosen_name,
                servable_key_expr(ProfilePhoto.media_id).label("storage_url"),
                ProfilePhoto.approved_at,
                ProfilePhoto.rejected_at,
                ProfilePhoto.created_at,
            )
            .join(DatingProfile, DatingProfile.id == ProfilePhoto.dating_profile_id)
            .join(Profile, Profile.id == DatingProfile.user_id)
            .where(ProfilePhoto.suggester_id == suggester_id)
            .order_by(desc(ProfilePhoto.created_at))
            .limit(limit)
        )
    ).all()

    return [
        SuggestedPhotoRow(
            id=photo_id,
            dater_id=dater_id,
            dater_name=dater_name,
            storage_url=storage_url,
            approved_at=approved_at,
            rejected_at=rejected_at,
            created_at=created_at,
        )
        for (photo_id, dater_id, dater_name, storage_url, approved_at, rejected_at, created_at) in rows
    ]


async def fetch_own_photos(db: AsyncSession, user_id: UUID) -> list[PhotoRow]:
    """All photos on the caller's dating profile, each with the suggester name.

    Join photo -> dating_profile (to scope to the caller) and left-join the suggester
    profile for its `chosen_name`, ordered by `display_order` ascending.
    """
    suggester = aliased(Profile)
    rows = (
        await db.execute(
            select(ProfilePhoto, suggester.chosen_name)
            .join(DatingProfile, DatingProfile.id == ProfilePhoto.dating_profile_id)
            .outerjoin(suggester, suggester.id == ProfilePhoto.suggester_id)
            .where(DatingProfile.user_id == user_id)
            .order_by(asc(ProfilePhoto.display_order))
        )
    ).all()
    return [(photo, name) for photo, name in rows]


async def fetch_photo_with_suggester(db: AsyncSession, photo_id: UUID) -> PhotoRow | None:
    """A single photo by id with its suggester chosen name (for action responses)."""
    suggester = aliased(Profile)
    row = (
        await db.execute(
            select(ProfilePhoto, suggester.chosen_name)
            .outerjoin(suggester, suggester.id == ProfilePhoto.suggester_id)
            .where(ProfilePhoto.id == photo_id)
            .limit(1)
        )
    ).first()
    if row is None:
        return None
    photo, name = row
    return photo, name


async def fetch_dating_profile_owner(db: AsyncSession, dating_profile_id: UUID) -> UUID | None:
    """The `user_id` that owns a dating profile, or None if it does not exist."""
    return (
        await db.execute(select(DatingProfile.user_id).where(DatingProfile.id == dating_profile_id).limit(1))
    ).scalar_one_or_none()


async def is_active_wingperson(db: AsyncSession, dater_id: UUID, winger_id: UUID) -> bool:
    """Whether `winger_id` is an active wingperson for `dater_id`."""
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


async def fetch_dater_push_and_suggester_name(
    db: AsyncSession, dater_id: UUID, suggester_id: UUID
) -> tuple[str | None, str | None]:
    """Return `(dater push_token, suggester chosen_name)` for the suggestion push.

    A single fetch over both ids.
    """
    rows = (
        await db.execute(
            select(Profile.id, Profile.push_token, Profile.chosen_name).where(Profile.id.in_([dater_id, suggester_id]))
        )
    ).all()
    dater_token: str | None = None
    suggester_name: str | None = None
    for pid, push_token, chosen_name in rows:
        if pid == dater_id:
            dater_token = push_token
        if pid == suggester_id:
            suggester_name = chosen_name
    return dater_token, suggester_name
