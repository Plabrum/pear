"""Row dataclass + snake_case -> camelCase mapper for the likes-you feed.

Ported from `supabase/functions/api/domains/likes-you/transformers.ts`. The query
in `app/domain/discover/queries.py` (shared FEED-cluster module) assembles
`LikesYouRow`; `row_to_likes_you_profile` maps it onto `LikesYouProfile`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.likes_you.schemas import LikesYouProfile
from app.domain.profiles.enums import Gender


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
    first_photo: str | None
    wing_note: str | None
    suggested_by: UUID | None
    suggester_name: str | None


def row_to_likes_you_profile(row: LikesYouRow) -> LikesYouProfile:
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
        firstPhoto=row.first_photo,
        wingNote=row.wing_note,
        suggestedBy=row.suggested_by,
        suggesterName=row.suggester_name,
    )
