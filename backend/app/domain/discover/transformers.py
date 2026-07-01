from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.discover.schemas import DiscoverProfile
from app.domain.profiles.enums import Gender
from app.platform.media.client import BaseMediaClient


@dataclass
class DiscoverRow:
    profile_id: UUID
    user_id: UUID
    chosen_name: str
    gender: Gender | None
    age: int
    city: City
    bio: str | None
    dating_status: DatingStatus
    interests: list[Interest]
    photos: list[str]  # S3 keys (approved only) — presigned at transform time
    wing_note: str | None
    suggested_by: UUID | None
    suggester_name: str | None


async def row_to_discover_profile(row: DiscoverRow, media: BaseMediaClient) -> DiscoverProfile:
    # `photos` are approved-only S3 keys (the query filters approved_at IS NOT NULL),
    # so presigning each one cannot leak an unapproved image.
    photos = [await media.presign_download(key) for key in (row.photos or [])]
    return DiscoverProfile(
        profileId=row.profile_id,
        userId=row.user_id,
        chosenName=row.chosen_name,
        gender=row.gender,
        age=row.age,
        city=row.city,
        bio=row.bio,
        datingStatus=row.dating_status,
        interests=row.interests,
        photos=photos,
        wingNote=row.wing_note,
        suggestedBy=row.suggested_by,
        suggesterName=row.suggester_name,
    )
