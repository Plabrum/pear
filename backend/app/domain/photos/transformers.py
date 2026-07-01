from __future__ import annotations

from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.models import ProfilePhoto
from app.domain.photos.queries import PhotoRow, SuggestedPhotoRow
from app.domain.photos.schemas import (
    Photo,
    PhotoSuggesterRef,
    SuggestedPhoto,
    SuggestedPhotoStatus,
)
from app.platform.actions.base import ActionGroup
from app.platform.actions.deps import ActionDeps
from app.platform.actions.hydrate import actions_for
from app.platform.media.client import BaseMediaClient
from app.utils.sqids import Sqid


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
        status=photo.state,
        suggesterId=photo.suggester_id,
        suggester=(
            PhotoSuggesterRef(id=photo.suggester_id, chosenName=suggester_name)
            if photo.suggester_id is not None
            else None
        ),
    )


def photos_to_dtos(
    rows: list[PhotoRow],
    url_by_media: dict[Sqid, str],
    group: ActionGroup,
    deps: ActionDeps,
) -> list[Photo]:
    """Map a batch of photo rows to DTOs, each carrying its resolved media URL and
    the actions available on it (approve/reject/delete — `reorder` is hidden)."""
    dtos: list[Photo] = []
    for photo, name in rows:
        dto = photo_to_dto(photo, name, url_by_media.get(photo.media_id))
        dto.actions = actions_for(group, deps, photo)
        dtos.append(dto)
    return dtos


def _suggested_status(row: SuggestedPhotoRow) -> SuggestedPhotoStatus:
    if row.state is PhotoApprovalState.REJECTED:
        return "not_accepted"
    if row.state is PhotoApprovalState.APPROVED:
        return "approved"
    return "pending"


async def suggested_photo_to_dto(row: SuggestedPhotoRow, media: BaseMediaClient) -> SuggestedPhoto:
    """Map a photo the caller suggested to its wire DTO, presigning its media key.

    `storage_url` holds the photo media's servable S3 key; serve a presigned GET
    URL. The read is scoped to the caller's OWN suggestions (`suggester_id = me`),
    so the visibility gate holds.
    """
    return SuggestedPhoto(
        id=row.id,
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        storageUrl=await media.presign_download(row.storage_url),
        status=_suggested_status(row),
        createdAt=row.created_at.isoformat() if row.created_at is not None else "",
    )
