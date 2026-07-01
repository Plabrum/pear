from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.domain.photos.models import ProfilePhoto
from app.domain.photos.queries import PhotoRow
from app.domain.photos.schemas import Photo, PhotoSuggesterRef


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


def photo_to_dto(photo: ProfilePhoto, suggester_name: str | None, url: str | None) -> Photo:
    """Map an ORM photo (+ joined suggester name) to the wire `Photo`.

    `storageUrl` is the resolved (presigned) media URL the caller already passed in
    — looked up by `photo.media_id` from a batched MediaService resolve. The caller
    must have authorized visibility before resolving. An unresolvable id yields ""."""
    return Photo(
        id=photo.id,
        datingProfileId=photo.dating_profile_id,
        storageUrl=url or "",
        displayOrder=photo.display_order,
        approvedAt=_iso(photo.approved_at),
        suggesterId=photo.suggester_id,
        suggester=(
            PhotoSuggesterRef(id=photo.suggester_id, chosenName=suggester_name)
            if photo.suggester_id is not None
            else None
        ),
    )


def photos_to_dtos(rows: list[PhotoRow], url_by_media: dict[UUID, str]) -> list[Photo]:
    """Map a batch of photo rows to DTOs, each carrying its resolved media URL."""
    return [photo_to_dto(photo, name, url_by_media.get(photo.media_id)) for photo, name in rows]
