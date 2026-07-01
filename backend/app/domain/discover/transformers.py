"""Row dataclass + snake_case -> camelCase mapper for the discover feed.

Ported from `supabase/functions/api/domains/discover/transformers.ts`. The query
in `queries.py` assembles `DiscoverRow` (snake_case, mirroring the Drizzle row
shape); `row_to_discover_profile` maps it onto the camelCase `DiscoverProfile`
struct the mobile app consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.discover.schemas import DiscoverProfile
from app.domain.profiles.enums import Gender


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
    photos: list[str]
    wing_note: str | None
    suggested_by: UUID | None
    suggester_name: str | None


def row_to_discover_profile(row: DiscoverRow) -> DiscoverProfile:
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
        photos=row.photos or [],
        wingNote=row.wing_note,
        suggestedBy=row.suggested_by,
        suggesterName=row.suggester_name,
    )
