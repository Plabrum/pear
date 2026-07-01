from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.likes_you.schemas import LikesYouProfile
from app.domain.profiles.enums import Gender
from app.platform.media.client import BaseMediaClient


@dataclass
class LikesYouRow:
    profile_id: UUID
    user_id: UUID
    chosen_name: str
    gender: Gender | None
    age: int
    city: City
    bio: str | None
    dating_status: DatingStatus
    interests: list[Interest]
    first_photo: str | None  # S3 key (approved only) — presigned at transform time
    wing_note: str | None
    suggested_by: UUID | None
    suggester_name: str | None


async def row_to_likes_you_profile(row: LikesYouRow, media: BaseMediaClient) -> LikesYouProfile:
    first_photo = await media.presign_download(row.first_photo) if row.first_photo is not None else None
    return LikesYouProfile(
        profileId=row.profile_id,
        userId=row.user_id,
        chosenName=row.chosen_name,
        gender=row.gender,
        age=row.age,
        city=row.city,
        bio=row.bio,
        datingStatus=row.dating_status,
        interests=row.interests,
        firstPhoto=first_photo,
        wingNote=row.wing_note,
        suggestedBy=row.suggested_by,
        suggesterName=row.suggester_name,
    )
