from __future__ import annotations

from litestar import Controller, Request, Router, delete, get, post
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.queries import is_active_wingperson
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient
from app.platform.media.exceptions import MediaNotFoundError
from app.platform.media.queries import fetch_media
from app.platform.media.schemas import (
    MediaResponse,
    PresignedUploadRequest,
    PresignedUploadResponse,
)
from app.platform.media.service import MediaService
from app.platform.queue.enums import TaskName
from app.platform.queue.transactions import dispatch_task
from app.utils.sqids import Sqid


class MediaController(Controller):
    """Upload-url / uploaded / get / delete for owner-scoped media."""

    path = "/media"

    @post("/upload-url", operation_id="postApiMediaUploadUrl")
    async def upload_url(
        self,
        data: PresignedUploadRequest,
        user: User,
        transaction: AsyncSession,
        media: BaseMediaClient,
    ) -> PresignedUploadResponse:
        """Create a PENDING Media owned by the caller + mint a presigned PUT.

        Any authenticated caller may create their OWN media (the row is owned by
        `user.id`); the key is rooted in the caller's folder.
        """
        service = MediaService(transaction, media)
        row = await service.create_for_owner(user.id, file_name=data.fileName, mime_type=data.contentType)
        presigned = await media.presign_upload(row.file_key, content_type=data.contentType)
        return PresignedUploadResponse(mediaId=row.id, uploadUrl=presigned.upload_url, key=presigned.key)

    @post("/{media_id:str}/uploaded", operation_id="postApiMediaUploaded")
    async def uploaded(
        self,
        media_id: Sqid,
        request: Request,
        user: User,
        transaction: AsyncSession,
    ) -> MediaResponse:
        """Owner-only: confirm the client finished its PUT and enqueue processing.

        The PENDING->PROCESSING transition is driven by the worker, not here. RLS
        scopes the fetch to the owner (or their active wingperson); a row the caller
        cannot see reads as 404.
        """
        row = await fetch_media(transaction, media_id)
        if row is None or row.owner_id != user.id:
            raise MediaNotFoundError()
        await dispatch_task(transaction, request, TaskName.PROCESS_IMAGE, media_id=int(row.id))
        return MediaResponse(id=row.id, state=str(row.state), url=row.file_key)

    @get("/{media_id:str}", operation_id="getApiMediaById")
    async def get_one(
        self,
        media_id: Sqid,
        user: User,
        transaction: AsyncSession,
        media: BaseMediaClient,
    ) -> MediaResponse:
        """Owner or active wingperson -> the resolved (best servable) URL.

        The media SELECT floor is broad (it mirrors photo visibility so feeds can
        presign other daters' approved photos). This direct-by-id route, though,
        only ever serves owned/winged media, so gate it explicitly — owner or the
        owner's active wingperson — and 404 otherwise, closing it as a presign oracle
        independent of the RLS policy.
        """
        row = await fetch_media(transaction, media_id)
        if row is None:
            raise MediaNotFoundError()
        if row.owner_id != user.id and not await is_active_wingperson(transaction, row.owner_id, user.id):
            raise MediaNotFoundError()
        service = MediaService(transaction, media)
        url = await service.resolve_url(row)
        return MediaResponse(id=row.id, state=str(row.state), url=url)

    @delete("/{media_id:str}", operation_id="deleteApiMediaById", status_code=204)
    async def delete_one(
        self,
        media_id: Sqid,
        transaction: AsyncSession,
        media: BaseMediaClient,
    ) -> None:
        """Owner or active wingperson (via RLS) -> delete the file, processed file, row."""
        row = await fetch_media(transaction, media_id)
        if row is None:
            raise MediaNotFoundError()
        await media.delete(row.file_key)
        if row.processed_key:
            await media.delete(row.processed_key)
        await transaction.delete(row)


media_router = Router(
    path="",
    route_handlers=[MediaController],
    tags=["media"],
    guards=[requires_session],
)
