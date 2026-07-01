from __future__ import annotations

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
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import resolve_group
from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.media.service import MediaService
from app.utils.sqids import Sqid


class ProfilesController(Controller):
    """GET /profiles/me, GET /profiles/{userId}."""

    path = "/profiles"

    @get("/me", operation_id="getApiProfilesMe")
    async def get_own_profile(
        self, user: User, transaction: AsyncSession, media_service: MediaService, action_deps: ActionDeps
    ) -> Profile:
        row = await fetch_profile(transaction, user.id)
        if row is None:
            raise NotFoundException("Profile not found")
        url_by_media = await media_service.resolve_urls(
            [row.avatar_media_id] if row.avatar_media_id is not None else []
        )
        profile_group = resolve_group(ActionGroupType.PROFILE_ACTIONS)
        return row_to_profile(row, url_by_media, profile_group, action_deps)

    @get("/{userId:str}", operation_id="getApiProfilesUserId")
    async def get_public_profile(
        self,
        userId: Sqid,
        user: User,
        transaction: AsyncSession,
        media_service: MediaService,
        action_deps: ActionDeps,
    ) -> PublicProfile:
        bundle = await fetch_public_profile(transaction, userId, user.id)
        if bundle is None:
            raise NotFoundException("Profile not found")
        profile, base, photos, prompts = bundle
        # The media SELECT policy mirrors profile_photos visibility, so a viewer can
        # read (and presign) the approved photos + the public avatar under their OWN
        # scope — no system mode, no elevated media-row access.
        url_by_media = await media_service.resolve_urls(public_media_ids(profile, photos))
        # The swipe group is one of two groups bound to DatingProfile, so resolve it
        # by explicit type (find_by_model would be ambiguous).
        swipe_group = resolve_group(ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS)
        return bundle_to_public_profile(profile, base, photos, prompts, url_by_media, swipe_group, action_deps)


class DatingProfilesController(Controller):
    """GET /dating-profiles/me."""

    path = "/dating-profiles"

    @get("/me", operation_id="getApiDatingProfilesMe")
    async def get_own_dating_profile(
        self, user: User, transaction: AsyncSession, media_service: MediaService, action_deps: ActionDeps
    ) -> OwnDatingProfileResponse:
        bundle = await fetch_own_dating_profile(transaction, user.id)
        if bundle is None:
            return None
        base, photos, prompts = bundle
        url_by_media = await media_service.resolve_urls(own_media_ids(photos, prompts))
        # The EDIT group (DATING_PROFILE_ACTIONS), not the swipe group, for the owner.
        dating_profile_group = resolve_group(ActionGroupType.DATING_PROFILE_ACTIONS)
        photo_group = resolve_group(ActionGroupType.PHOTO_ACTIONS)
        prompt_group = resolve_group(ActionGroupType.PROFILE_PROMPT_ACTIONS)
        response_group = resolve_group(ActionGroupType.PROMPT_RESPONSE_ACTIONS)
        return dating_profile_to_own(
            base,
            photos,
            prompts,
            url_by_media,
            dating_profile_group,
            photo_group,
            prompt_group,
            response_group,
            action_deps,
        )


profiles_router = Router(
    path="",
    route_handlers=[ProfilesController, DatingProfilesController],
    tags=["profiles"],
    guards=[requires_session],
)
