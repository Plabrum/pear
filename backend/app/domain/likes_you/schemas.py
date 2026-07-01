"""msgspec schemas for the likes-you domain (READS ONLY).

Ported from `supabase/functions/api/domains/likes-you/schemas.ts`. camelCase field
names match the Hono Zod output byte-for-byte. `LikesYouProfile` is the pool item
(Hono `LikesYouResponse` is an array of these); `LikesYouCountResponse` is the
`/likes-you/count` body. The Hono `LikesYouQuery` becomes typed paging params on
the pool handler.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.profiles.enums import Gender
from app.platform.base.schemas import BaseSchema


class LikesYouProfile(BaseSchema):
    profileId: UUID
    userId: UUID
    chosenName: str
    gender: Gender | None
    age: int
    city: City
    bio: str | None
    datingStatus: DatingStatus
    interests: list[Interest]
    firstPhoto: str | None
    wingNote: str | None
    suggestedBy: UUID | None
    suggesterName: str | None


class LikesYouCountResponse(BaseSchema):
    count: int
