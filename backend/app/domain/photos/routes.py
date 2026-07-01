from __future__ import annotations

from litestar import Controller, Router, get
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.queries import fetch_own_photos
from app.domain.photos.schemas import OwnPhotosResponse
from app.domain.photos.transformers import photos_to_dtos
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.service import MediaService


class PhotosController(Controller):
    """GET /photos/me — the caller's own photos, each with a resolved media URL."""

    path = "/photos"

    @get("/me", operation_id="getApiPhotosMe")
    async def list_own_photos(
        self, user: User, transaction: AsyncSession, media_service: MediaService
    ) -> OwnPhotosResponse:
        """The caller's OWN photos (pending + approved — the editor shows both).

        Ownership satisfies the read gate, so the media URLs are resolved in one
        batched system-mode pass (resolve_urls_system) keyed by each photo's media_id.
        """
        rows = await fetch_own_photos(transaction, user.id)
        url_by_media = await media_service.resolve_urls_system([photo.media_id for photo, _ in rows])
        return photos_to_dtos(rows, url_by_media)


photos_router = Router(
    path="",
    route_handlers=[PhotosController],
    tags=["photos"],
    guards=[requires_session],
)
