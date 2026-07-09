from __future__ import annotations

import logging

import msgspec
from litestar import Response

from app.config import Config
from app.platform.updates.models import AppUpdate
from app.platform.updates.schemas import ManifestResponse, UpdateAsset, UpdateManifest
from app.platform.updates.signing import sign_manifest

logger = logging.getLogger(__name__)


# ─── Manifest protocol v2 (GET /updates/v2/manifest) ───────────────────────────


def build_update_manifest(row: AppUpdate) -> UpdateManifest:
    """Convert a stored `AppUpdate` row into the v2 wire shape.

    `row.launch_asset`/`row.assets` are JSONB dicts keyed in the v1 protocol's
    camelCase (`contentType`, `fileExtension`) — the shape `PublishUpdateRequest`
    stores verbatim (see `models.py`). `build-ota-payload.js`'s publish payload is
    unaffected by this route, so the stored keys stay camelCase; only this v2 read
    path re-keys them to snake_case for the new client.
    """
    launch_asset = row.launch_asset
    return UpdateManifest(
        update_uuid=str(row.update_uuid),
        created_at=row.created_at.isoformat(),
        runtime_version=row.runtime_version,
        launch_asset=UpdateAsset(
            key=launch_asset["key"],
            content_type=launch_asset["contentType"],
            url=launch_asset["url"],
            hash=launch_asset["hash"],
        ),
        assets=[
            UpdateAsset(
                key=asset["key"],
                content_type=asset["contentType"],
                url=asset["url"],
                hash=asset["hash"],
                file_extension=asset.get("fileExtension"),
            )
            for asset in row.assets
        ],
    )


def manifest_v2_response(response: ManifestResponse, config: Config) -> Response[bytes]:
    """Sign the entire raw JSON body — no multipart wrapping, no RFC 8941
    Structured Field Value formatting, no ambiguity about which bytes were signed.
    """
    body = msgspec.json.encode(response)
    signature = sign_manifest(body, config)
    headers = {"cache-control": "private, no-cache"}
    if signature is not None:
        headers["x-update-signature"] = signature
        headers["x-update-signing-key-id"] = config.UPDATES_SIGNING_KEY_ID
    else:
        logger.warning("updates: serving v2 manifest UNSIGNED (no UPDATES_SIGNING_PRIVATE_KEY configured)")
    return Response(content=body, media_type="application/json", headers=headers)
