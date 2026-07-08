from __future__ import annotations

import logging

import msgspec
from litestar import Request, Response, get, post
from litestar.exceptions import ClientException
from litestar.params import Parameter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.platform.auth.guards import requires_updates_publish_token
from app.platform.updates.enums import RolloutStatus, UpdateChannel, UpdatePlatform
from app.platform.updates.models import AppUpdate, NativeBuildFingerprint
from app.platform.updates.protocol import directive_response, manifest_response
from app.platform.updates.queries import latest_relevant_update
from app.platform.updates.schemas import (
    NativeBuildFingerprintResponse,
    NoUpdateAvailableDirective,
    PublishUpdateRequest,
    PublishUpdateResponse,
    RollBackDirective,
    RollBackDirectiveParameters,
    SetNativeBuildFingerprintRequest,
)

logger = logging.getLogger(__name__)


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

    logger.info(
        "updates/manifest request: runtime_version=%s platform=%s channel=%s current_update_id=%s ip=%s",
        runtime_version,
        platform_header,
        channel_header,
        current_update_id,
        request.client.host if request.client else None,
    )

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
        logger.info("updates/manifest: no update row for runtime_version=%s channel=%s", runtime_version, channel)
        return directive_response(NoUpdateAvailableDirective(), app_config)

    if current_update_id and current_update_id.strip().lower() == str(row.update_uuid):
        logger.info("updates/manifest: client already on latest update_uuid=%s", row.update_uuid)
        return directive_response(NoUpdateAvailableDirective(), app_config)

    if row.rollout == RolloutStatus.ROLLED_BACK:
        logger.info("updates/manifest: serving rollback directive for update_uuid=%s", row.update_uuid)
        return directive_response(
            RollBackDirective(parameters=RollBackDirectiveParameters(createdAt=row.created_at.isoformat())),
            app_config,
        )

    logger.info("updates/manifest: serving manifest for update_uuid=%s", row.update_uuid)
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


@post(
    "/updates/native-build-fingerprint",
    exclude_from_auth=True,
    guards=[requires_updates_publish_token],
)
async def set_native_build_fingerprint(
    data: SetNativeBuildFingerprintRequest, transaction: AsyncSession
) -> NativeBuildFingerprintResponse:
    """CI-only: `ci_post_xcodebuild.sh` calls this after every successful Xcode
    Cloud native archive. Upserts the one row for `data.platform` - this tracks
    "the current native build's fingerprint," not an audit log, so a second call
    for the same platform overwrites rather than duplicates. Reuses
    `requires_updates_publish_token` rather than minting a dedicated credential —
    one fewer secret to provision in the Xcode Cloud workflow settings.
    """
    row = (
        await transaction.execute(
            select(NativeBuildFingerprint).where(NativeBuildFingerprint.platform == data.platform)
        )
    ).scalar_one_or_none()
    if row is None:
        row = NativeBuildFingerprint(platform=data.platform, fingerprint=data.fingerprint)
        transaction.add(row)
    else:
        row.fingerprint = data.fingerprint
    await transaction.flush()
    return NativeBuildFingerprintResponse(platform=row.platform, fingerprint=row.fingerprint)


@get("/updates/native-build-fingerprint", exclude_from_auth=True)
async def get_native_build_fingerprint(
    transaction: AsyncSession, platform: UpdatePlatform = Parameter(query="platform")
) -> NativeBuildFingerprintResponse:
    """Unauthenticated: a fingerprint hash isn't sensitive. `ota.yml`'s fingerprint
    guardrail calls this instead of reading a GitHub Actions variable that Xcode
    Cloud has no automated way to write back to.
    """
    row = (
        await transaction.execute(select(NativeBuildFingerprint).where(NativeBuildFingerprint.platform == platform))
    ).scalar_one_or_none()
    return NativeBuildFingerprintResponse(platform=platform, fingerprint=row.fingerprint if row else None)
