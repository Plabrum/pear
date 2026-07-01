"""snake_case ORM rows -> camelCase msgspec structs for the photos domain.

Ported from `supabase/functions/api/domains/photos/transformers.ts`. The Hono
`rowToPhoto` mapped a flat Drizzle row (carrying the joined suggester chosen_name)
onto the Zod `Photo` shape; here we map a `(ProfilePhoto, suggester_name | None)`
pair onto the msgspec `Photo` struct. `approved_at` (a `timestamptz`) renders as an
ISO-8601 string to match the JSON contract the mobile app already consumes.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.photos.models import ProfilePhoto
from app.domain.photos.schemas import Photo, PhotoSuggesterRef


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def photo_to_dto(photo: ProfilePhoto, suggester_name: str | None) -> Photo:
    """Map an ORM photo (+ the joined suggester chosen_name) to the wire `Photo`."""
    return Photo(
        id=photo.id,
        datingProfileId=photo.dating_profile_id,
        storageUrl=photo.storage_url,
        displayOrder=photo.display_order,
        approvedAt=_iso(photo.approved_at),
        suggesterId=photo.suggester_id,
        suggester=(
            PhotoSuggesterRef(id=photo.suggester_id, chosenName=suggester_name)
            if photo.suggester_id is not None
            else None
        ),
    )
