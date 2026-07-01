from __future__ import annotations

from datetime import datetime

from app.domain.photos.models import ProfilePhoto
from app.domain.photos.schemas import Photo, PhotoSuggesterRef
from app.platform.media.client import BaseMediaClient


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value is not None else None


async def photo_to_dto(photo: ProfilePhoto, suggester_name: str | None, media: BaseMediaClient) -> Photo:
    """Map an ORM photo (+ joined suggester name) to the wire `Photo`.

    `storageUrl` is a presigned GET URL for the stored S3 key. The caller must have
    already RLS-gated visibility (own photos / approved-public) before issuing it.
    """
    return Photo(
        id=photo.id,
        datingProfileId=photo.dating_profile_id,
        storageUrl=await media.presign_download(photo.storage_url),
        displayOrder=photo.display_order,
        approvedAt=_iso(photo.approved_at),
        suggesterId=photo.suggester_id,
        suggester=(
            PhotoSuggesterRef(id=photo.suggester_id, chosenName=suggester_name)
            if photo.suggester_id is not None
            else None
        ),
    )
