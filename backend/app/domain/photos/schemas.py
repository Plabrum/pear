from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── Output ───────────────────────────────────────────────────────────────────


class PhotoSuggesterRef(BaseSchema):
    id: UUID
    chosenName: str | None


class Photo(BaseSchema):
    id: UUID
    datingProfileId: UUID
    storageUrl: str
    displayOrder: int
    approvedAt: str | None
    suggesterId: UUID | None
    suggester: PhotoSuggesterRef | None


# GET /photos/me returns a bare JSON array of photos.
OwnPhotosResponse = list[Photo]


class PhotosOkResponse(BaseSchema):
    """`{ ok: true }` — reject / delete success body."""

    ok: Literal[True] = True


class PhotoUploadUrlResponse(BaseSchema):
    """Presigned S3 PUT target. The client `PUT`s bytes to `uploadUrl`, then sends
    `key` as `storageUrl` in POST /photos. `key` is `<ownerId>/<uuid>.<ext>`."""

    uploadUrl: str
    key: str


class AvatarUploadUrlResponse(BaseSchema):
    """Presigned S3 PUT target for the caller's avatar (public-read key).

    After `PUT`ting bytes to `uploadUrl`, the client PATCHes `avatarUrl = key` on
    its profile; `publicUrl` is the stable URL the avatar will resolve to for reads."""

    uploadUrl: str
    key: str
    publicUrl: str


# ── Input ────────────────────────────────────────────────────────────────────


class CreatePhotoData(BaseSchema):
    """POST /photos body — create photo metadata (dater or active wingperson)."""

    datingProfileId: UUID
    storageUrl: str
    displayOrder: int


class ReorderPhotoData(BaseSchema):
    """PATCH /photos/{id}/reorder body."""

    displayOrder: int


class PhotoUploadUrlData(BaseSchema):
    """POST /photos/upload-url body — request a presigned PUT for a profile photo.

    `contentType` is the MIME type the client will set on the PUT (the client
    resizes to JPEG before upload, so it defaults to image/jpeg)."""

    datingProfileId: UUID
    filename: str
    contentType: str = "image/jpeg"


class AvatarUploadUrlData(BaseSchema):
    """POST /profiles/me/avatar-upload-url body — request a presigned PUT for the
    caller's own avatar."""

    filename: str
    contentType: str = "image/jpeg"
