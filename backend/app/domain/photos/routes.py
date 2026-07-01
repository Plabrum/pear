from __future__ import annotations

from litestar import Controller, Router, get
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.queries import fetch_own_photos, fetch_suggested_photos
from app.domain.photos.schemas import OwnPhotosResponse, SuggestedPhotosResponse
from app.domain.photos.transformers import photos_to_dtos, suggested_photo_to_dto
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import resolve_group
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient
from app.platform.media.service import MediaService


class PhotosController(Controller):
    """GET /photos/me + GET /photos/suggested — the caller's photos by relationship."""

    path = "/photos"

    @get("/me", operation_id="getApiPhotosMe")
    async def list_own_photos(
        self, user: User, transaction: AsyncSession, media_service: MediaService, action_deps: ActionDeps
    ) -> OwnPhotosResponse:
        """The caller's OWN photos (pending + approved — the editor shows both).

        Ownership satisfies the media SELECT policy, so the URLs are resolved under
        the caller's own scope in one batched pass keyed by each photo's media_id.
        Each photo carries the actions available on it (approve/reject/delete).
        """
        rows = await fetch_own_photos(transaction, user.id)
        url_by_media = await media_service.resolve_urls([photo.media_id for photo, _ in rows])
        photo_group = resolve_group(ActionGroupType.PHOTO_ACTIONS)
        return photos_to_dtos(rows, url_by_media, photo_group, action_deps)

    @get("/suggested", operation_id="getApiPhotosSuggested")
    async def list_suggested_photos(
        self,
        user: User,
        transaction: AsyncSession,
        media: BaseMediaClient,
        limit: int = Parameter(query="limit", default=50, ge=1, le=100),
    ) -> SuggestedPhotosResponse:
        """Photos the caller suggested as a winger (`suggester_id = me`), newest first.

        The read is scoped to the caller's own suggestions, so each row's media URL is
        presigned directly — the suggester is authorized to see what they proposed.
        """
        rows = await fetch_suggested_photos(transaction, user.id, limit)
        return [await suggested_photo_to_dto(row, media) for row in rows]


photos_router = Router(
    path="",
    route_handlers=[PhotosController],
    tags=["photos"],
    guards=[requires_session],
)
