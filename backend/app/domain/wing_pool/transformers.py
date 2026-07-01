"""Row dataclass + snake_case -> camelCase mapper for the wing-pool feed.

Ported from `supabase/functions/api/domains/wing-pool/transformers.ts`. The query
in `app/domain/discover/queries.py` (shared FEED-cluster module) assembles
`WingPoolRow`; `row_to_wing_profile` maps it onto the camelCase `WingProfile`.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.profiles.enums import Gender
from app.domain.wing_pool.schemas import WingProfile


@dataclass
class WingPoolRow:
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


def row_to_wing_profile(row: WingPoolRow) -> WingProfile:
    return WingProfile(
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
    )
