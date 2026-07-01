"""Read + presigned-upload endpoints for the photos domain.

Ported from the GET / upload-url handlers in
`supabase/functions/api/domains/photos/route.ts`. All *mutations* (create, approve,
reject, delete, reorder) live in `actions.py`; this module holds only:

  * GET  /photos/me        — the caller's own photos (a self-collection join, so an
                             explicit `@get` handler rather than the declarative
                             `make_crud_controller`, which assumes list-by-row-id).
  * POST /photos/upload-url — mint a presigned upload token. This is a POST but NOT a
                             database mutation — it authorizes the caller then returns
                             a `{path, uploadToken}` RPC result. The storage call is a
                             Phase-6 stub (see the handler). Keeping it here preserves
                             the `{path, uploadToken}` wire contract the mobile app
                             consumes (an action's `ActionExecutionResponse` envelope
                             would change that shape).

RLS enforces access; the transformers map ORM rows -> camelCase structs.
"""

from __future__ import annotations

import uuid

from litestar import Controller, Router, get, post
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
)
from app.domain.photos.queries import (
    fetch_dating_profile_owner,
    fetch_own_photos,
    is_active_wingperson,
)
from app.domain.photos.schemas import (
    OwnPhotosResponse,
    PhotoUploadUrlData,
    PhotoUploadUrlResponse,
)
from app.domain.photos.transformers import photo_to_dto
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User


def _ext_from_filename(filename: str) -> str:
    """Match Hono's extension parse: the part after the last dot, else 'jpg'."""
    dot = filename.rfind(".")
    if 0 < dot < len(filename) - 1:
        return filename[dot + 1 :]
    return "jpg"


class PhotosController(Controller):
    """GET /photos/me and POST /photos/upload-url."""

    path = "/photos"

    @get("/me", operation_id="getApiPhotosMe")
    async def list_own_photos(self, user: User, transaction: AsyncSession) -> OwnPhotosResponse:
        rows = await fetch_own_photos(transaction, user.id)
        return [photo_to_dto(photo, name) for photo, name in rows]

    @post("/upload-url", operation_id="postApiPhotosUploadUrl")
    async def photo_upload_url(
        self, data: PhotoUploadUrlData, user: User, transaction: AsyncSession
    ) -> PhotoUploadUrlResponse:
        owner_id = await fetch_dating_profile_owner(transaction, data.datingProfileId)
        if owner_id is None:
            raise DatingProfileNotFoundError()

        if owner_id != user.id and not await is_active_wingperson(transaction, owner_id, user.id):
            raise NotDaterOrWingpersonError()

        ext = _ext_from_filename(data.filename)
        path = f"{owner_id}/{uuid.uuid4()}.{ext}"
        # TODO(Phase 6): mint a real signed upload token into the profile-photos
        # bucket (Hono's createSignedUploadToken). Until storage lands, return a
        # placeholder token so the endpoint shape is stable for the client.
        upload_token = ""  # noqa: S105 — placeholder until Phase 6 storage
        return PhotoUploadUrlResponse(path=path, uploadToken=upload_token)


photos_router = Router(
    path="",
    route_handlers=[PhotosController],
    tags=["photos"],
    guards=[requires_session],
)
