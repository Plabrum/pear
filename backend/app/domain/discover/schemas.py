"""msgspec schemas for the discover domain (READS ONLY).

Ported from `supabase/functions/api/domains/discover/schemas.ts`. camelCase field
names match the Hono Zod output byte-for-byte (the mobile app's Orval hooks consume
these). Enum-typed fields use the domain `Enum` classes directly; msgspec
serializes an Enum by its `.value`, which is exactly the wire form the Zod enums
emit (`'open'`, `'Boston'`, `'Male'`, …).

`DiscoverProfile` is the response item (the Hono `DiscoverResponse` is an array of
these). The Hono query string (`DiscoverQuery`) becomes the typed query params on
the route handler — see `routes.py`.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.profiles.enums import Gender
from app.platform.base.schemas import BaseSchema


class DiscoverProfile(BaseSchema):
    profileId: UUID
    userId: UUID
    chosenName: str
    gender: Gender | None
    age: int
    city: City
    bio: str | None
    datingStatus: DatingStatus
    interests: list[Interest]
    photos: list[str]
    wingNote: str | None
    suggestedBy: UUID | None
    suggesterName: str | None
