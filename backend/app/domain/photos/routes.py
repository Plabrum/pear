from __future__ import annotations

from litestar import Controller, Router, get, post
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.queries import fetch_own_photos
from app.domain.photos.schemas import (
    OwnPhotosResponse,
    PhotoUploadUrlData,
    PhotoUploadUrlResponse,
)
from app.domain.photos.storage import presign_photo_upload
from app.domain.photos.transformers import photo_to_dto
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient


class PhotosController(Controller):
    """GET /photos/me and POST /photos/upload-url."""

    path = "/photos"

    @get("/me", operation_id="getApiPhotosMe")
    async def list_own_photos(self, user: User, transaction: AsyncSession, media: BaseMediaClient) -> OwnPhotosResponse:
        rows = await fetch_own_photos(transaction, user.id)
        # These are the caller's OWN photos — ownership satisfies the read gate, so
        # we presign every one (pending/approved alike, as the editor shows both).
        return [await photo_to_dto(photo, name, media) for photo, name in rows]

    @post("/upload-url", operation_id="postApiPhotosUploadUrl")
    async def photo_upload_url(
        self,
        data: PhotoUploadUrlData,
        user: User,
        transaction: AsyncSession,
        media: BaseMediaClient,
    ) -> PhotoUploadUrlResponse:
        # Authorize the own-folder write + mint the presigned PUT (see storage.py).
        return await presign_photo_upload(
            transaction,
            caller_id=user.id,
            dating_profile_id=data.datingProfileId,
            filename=data.filename,
            content_type=data.contentType,
            media=media,
        )


photos_router = Router(
    path="",
    route_handlers=[PhotosController],
    tags=["photos"],
    guards=[requires_session],
)
