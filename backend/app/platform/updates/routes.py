from __future__ import annotations

import logging

import msgspec
from litestar import Response, get, post
from litestar.params import Parameter
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.platform.auth.guards import requires_updates_publish_token
from app.platform.updates.enums import RolloutStatus, UpdateChannel, UpdatePlatform
from app.platform.updates.models import AppUpdate
from app.platform.updates.protocol import build_update_manifest, manifest_v2_response
from app.platform.updates.queries import latest_relevant_update
from app.platform.updates.schemas import (
    ClientEventRequest,
    ManifestResponse,
    PublishUpdateRequest,
    PublishUpdateResponse,
)

logger = logging.getLogger(__name__)


@get("/updates/v2/manifest", exclude_from_auth=True)
async def get_manifest_v2(
    transaction: AsyncSession,
    runtime_version: str = Parameter(query="runtime_version"),
    channel: UpdateChannel = Parameter(query="channel"),
    platform: UpdatePlatform = Parameter(query="platform"),
    current_update_id: str | None = Parameter(query="current_update_id", default=None),
) -> Response[bytes]:
    """Plain-JSON, snake_case manifest endpoint — speaks our own wire contract to
    our own custom OTA client, not the `expo-updates` protocol. Query params
    instead of `expo-*` request headers since this is no longer shaped by
    another client's spec.
    """
    logger.info(
        "updates/v2/manifest request: runtime_version=%s platform=%s channel=%s current_update_id=%s",
        runtime_version,
        platform,
        channel,
        current_update_id,
    )

    row = await latest_relevant_update(
        transaction,
        runtime_version=runtime_version,
        channel=channel,
        platform=platform,
    )

    if row is None:
        logger.info("updates/v2/manifest: no update row for runtime_version=%s channel=%s", runtime_version, channel)
        return manifest_v2_response(ManifestResponse(status="no_update"), app_config)

    if current_update_id and current_update_id.strip().lower() == str(row.update_uuid):
        logger.info("updates/v2/manifest: client already on latest update_uuid=%s", row.update_uuid)
        return manifest_v2_response(ManifestResponse(status="no_update"), app_config)

    if row.rollout == RolloutStatus.ROLLED_BACK:
        logger.info("updates/v2/manifest: serving rollback for update_uuid=%s", row.update_uuid)
        return manifest_v2_response(
            ManifestResponse(status="rollback", rollback_created_at=row.created_at.isoformat()),
            app_config,
        )

    logger.info("updates/v2/manifest: serving manifest for update_uuid=%s", row.update_uuid)
    return manifest_v2_response(
        ManifestResponse(status="update_available", manifest=build_update_manifest(row)),
        app_config,
    )


@post("/updates/client-event", exclude_from_auth=True)
async def post_client_event(data: ClientEventRequest) -> None:
    """Fired by the Swift OTA client on download failure, verify failure, apply,
    and rollback — the direct fix for "no useful signal": these become visible
    here in server logs instead of only discoverable via a support ticket or a
    device in hand. Log-only (no DB write) — an observability signal, not a
    record that needs to be queried back.
    """
    logger.info(
        "updates/client-event: event=%s runtime_version=%s update_uuid=%s detail=%s",
        data.event,
        data.runtime_version,
        data.update_uuid,
        data.detail,
    )


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
