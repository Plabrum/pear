from __future__ import annotations

import msgspec
from litestar import Request, Response, get, post
from litestar.exceptions import ClientException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.platform.auth.guards import requires_updates_publish_token
from app.platform.updates.enums import RolloutStatus, UpdateChannel, UpdatePlatform
from app.platform.updates.models import AppUpdate
from app.platform.updates.protocol import directive_response, manifest_response
from app.platform.updates.queries import latest_relevant_update
from app.platform.updates.schemas import (
    NoUpdateAvailableDirective,
    PublishUpdateRequest,
    PublishUpdateResponse,
    RollBackDirective,
    RollBackDirectiveParameters,
)


@get("/updates/manifest", exclude_from_auth=True)
async def get_manifest(request: Request, transaction: AsyncSession) -> Response[bytes]:
    """Expo Updates protocol v1 manifest endpoint — mounted at the root (like
    `/ws`), NOT under the auth-gated `/api`: `expo-updates` on the client speaks
    this protocol unauthenticated, with its own header set, not a session cookie.
    """
    runtime_version = request.headers.get("expo-runtime-version")
    platform_header = request.headers.get("expo-platform")
    channel_header = request.headers.get("expo-channel-name")
    current_update_id = request.headers.get("expo-current-update-id")

    if not runtime_version or not platform_header or not channel_header:
        raise ClientException("Missing required expo-runtime-version / expo-platform / expo-channel-name headers")

    try:
        platform = UpdatePlatform(platform_header)
        channel = UpdateChannel(channel_header)
    except ValueError as exc:
        raise ClientException(f"Unsupported expo-platform/expo-channel-name: {exc}") from exc

    row = await latest_relevant_update(
        transaction,
        runtime_version=runtime_version,
        channel=channel,
        platform=platform,
    )

    # No published update for this tuple yet — fail safe to "nothing to apply"
    # rather than erroring the client's update check.
    if row is None:
        return directive_response(NoUpdateAvailableDirective())

    if current_update_id and current_update_id.strip().lower() == str(row.update_uuid):
        return directive_response(NoUpdateAvailableDirective())

    if row.rollout == RolloutStatus.ROLLED_BACK:
        return directive_response(
            RollBackDirective(parameters=RollBackDirectiveParameters(createdAt=row.created_at.isoformat()))
        )

    return manifest_response(row, app_config)


@post("/updates/publish", exclude_from_auth=True, guards=[requires_updates_publish_token])
async def publish_update(data: PublishUpdateRequest, transaction: AsyncSession) -> PublishUpdateResponse:
    """CI-only: `ota.yml` calls this after uploading a bundle + assets to S3, so the
    backend can register the new `app_updates` row.

    Not a user-facing action — there's no session (bearer-token guarded, not
    `requires_session`) — so this bypasses the domain actions/state-machine
    framework and inserts directly. `app_updates` has no RLS (see `models.py`), so
    there's no `is_system_mode()` floor to satisfy and no need to route this
    through the task/worker layer — the bearer-token guard on this route is the
    actual security floor.
    """
    row = AppUpdate(
        runtime_version=data.runtimeVersion,
        channel=data.channel,
        platform=data.platform,
        launch_asset=msgspec.to_builtins(data.launchAsset),
        assets=[msgspec.to_builtins(asset) for asset in data.assets],
        rollout=RolloutStatus.LIVE,
    )
    transaction.add(row)
    await transaction.flush()
    return PublishUpdateResponse(id=row.id, updateUuid=str(row.update_uuid))
