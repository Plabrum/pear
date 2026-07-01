from __future__ import annotations

from uuid import UUID

from litestar import Controller, Router, get
from litestar.exceptions import NotFoundException
from sqlalchemy.ext.asyncio import AsyncSession

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
    own_media_ids,
    public_media_ids,
    row_to_profile,
)
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.service import MediaService


class ProfilesController(Controller):
    """GET /profiles/me, GET /profiles/{userId}."""

    path = "/profiles"

    @get("/me", operation_id="getApiProfilesMe")
    async def get_own_profile(self, user: User, transaction: AsyncSession, media_service: MediaService) -> Profile:
        row = await fetch_profile(transaction, user.id)
        if row is None:
            raise NotFoundException("Profile not found")
        url_by_media = await media_service.resolve_urls_system(
            [row.avatar_media_id] if row.avatar_media_id is not None else []
        )
        return row_to_profile(row, url_by_media)

    @get("/{userId:uuid}", operation_id="getApiProfilesUserId")
    async def get_public_profile(
        self, userId: UUID, user: User, transaction: AsyncSession, media_service: MediaService
    ) -> PublicProfile:
        bundle = await fetch_public_profile(transaction, userId)
        if bundle is None:
            raise NotFoundException("Profile not found")
        profile, base, photos, prompts = bundle
        # RLS already authorized this read (approved-only photos); resolve every
        # referenced media id in one batched system-mode pass so a matched viewer
        # gets the approved photo + avatar URLs without direct media-row access.
        url_by_media = await media_service.resolve_urls_system(public_media_ids(profile, photos))
        return bundle_to_public_profile(profile, base, photos, prompts, url_by_media)


class DatingProfilesController(Controller):
    """GET /dating-profiles/me."""

    path = "/dating-profiles"

    @get("/me", operation_id="getApiDatingProfilesMe")
    async def get_own_dating_profile(
        self, user: User, transaction: AsyncSession, media_service: MediaService
    ) -> OwnDatingProfileResponse:
        bundle = await fetch_own_dating_profile(transaction, user.id)
        if bundle is None:
            return None
        base, photos, prompts = bundle
        url_by_media = await media_service.resolve_urls_system(own_media_ids(photos, prompts))
        return dating_profile_to_own(base, photos, prompts, url_by_media)


profiles_router = Router(
    path="",
    route_handlers=[ProfilesController, DatingProfilesController],
    tags=["profiles"],
    guards=[requires_session],
)
