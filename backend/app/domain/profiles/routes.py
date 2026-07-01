from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get, post
from litestar.exceptions import NotFoundException
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.schemas import AvatarUploadUrlData, AvatarUploadUrlResponse
from app.domain.photos.storage import presign_avatar_upload
from app.domain.profiles.queries import (
    fetch_own_dating_profile,
    fetch_profile,
    fetch_public_profile,
)
from app.domain.profiles.schemas import (
    OwnDatingProfileResponse,
    Profile,
    PublicProfile,
)
from app.domain.profiles.transformers import (
    bundle_to_public_profile,
    dating_profile_to_own,
    row_to_profile,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.client import BaseMediaClient


class ProfilesController(Controller):
    """GET /profiles/me, GET /profiles/{userId}, POST /profiles/me/avatar-upload-url."""

    path = "/profiles"

    @get("/me", operation_id="getApiProfilesMe")
    async def get_own_profile(self, user: User, transaction: AsyncSession, media: BaseMediaClient) -> Profile:
        row = await fetch_profile(transaction, user.id)
        if row is None:
            raise NotFoundException("Profile not found")
        return row_to_profile(row, media)

    @get("/{userId:uuid}", operation_id="getApiProfilesUserId")
    async def get_public_profile(
        self, userId: UUID, user: User, transaction: AsyncSession, media: BaseMediaClient
    ) -> PublicProfile:
        bundle = await fetch_public_profile(transaction, userId)
        if bundle is None:
            raise NotFoundException("Profile not found")
        profile, base, photos, prompts = bundle
        return await bundle_to_public_profile(profile, base, photos, prompts, media)

    @post("/me/avatar-upload-url", operation_id="postApiProfilesMeAvatarUploadUrl")
    async def avatar_upload_url(
        self, data: AvatarUploadUrlData, user: User, media: BaseMediaClient
    ) -> AvatarUploadUrlResponse:
        """Mint a presigned PUT for the CALLER's own avatar (public-read key).

        Own-folder write: the key is rooted in the authenticated user's id, so a
        caller can only ever write their own avatar (see `presign_avatar_upload`)."""
        return await presign_avatar_upload(
            caller_id=user.id,
            filename=data.filename,
            content_type=data.contentType,
            media=media,
        )


class DatingProfilesController(Controller):
    """GET /dating-profiles/me."""

    path = "/dating-profiles"

    @get("/me", operation_id="getApiDatingProfilesMe")
    async def get_own_dating_profile(
        self, user: User, transaction: AsyncSession, media: BaseMediaClient
    ) -> OwnDatingProfileResponse:
        bundle = await fetch_own_dating_profile(transaction, user.id)
        if bundle is None:
            return None
        base, photos, prompts = bundle
        return await dating_profile_to_own(base, photos, prompts, media)


profiles_router = Router(
    path="",
    route_handlers=[ProfilesController, DatingProfilesController],
    tags=["profiles"],
    guards=[requires_session],
)
