from __future__ import annotations

from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── Input ────────────────────────────────────────────────────────────────────


class PresignedUploadRequest(BaseSchema):
    """POST /media/upload-url body — request a presigned PUT for a new media object."""

    fileName: str
    contentType: str = "image/jpeg"


# ── Output ───────────────────────────────────────────────────────────────────


class PresignedUploadResponse(BaseSchema):
    """Presigned PUT target plus the freshly-created Media row's id.

    The client `PUT`s the image bytes to `uploadUrl`, then calls
    POST /media/{mediaId}/uploaded to kick off processing. `key` is the original
    upload key (the same value persisted as the Media's `file_key`)."""

    mediaId: Sqid
    uploadUrl: str
    key: str


class MediaResponse(BaseSchema):
    """A resolved media object — `url` is the best available (READY processed key,
    else the original) presigned/public URL for the current `state`."""

    id: Sqid
    state: str
    url: str
