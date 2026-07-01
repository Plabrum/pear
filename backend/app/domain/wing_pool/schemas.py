"""msgspec schemas for the wing-pool domain (READS ONLY).

Ported from `supabase/functions/api/domains/wing-pool/schemas.ts`. camelCase field
names match the Hono Zod output byte-for-byte. `WingProfile` is the response item
(Hono `WingPoolResponse` is an array of these); the Hono `WingPoolQuery` becomes
typed query params on the route handler (`daterId` required, paging).
"""

from __future__ import annotations

from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.profiles.enums import Gender
from app.platform.base.schemas import BaseSchema


class WingProfile(BaseSchema):
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
