from __future__ import annotations

from typing import Literal

from app.platform.base.schemas import BaseSchema
from app.platform.updates.enums import UpdateChannel, UpdatePlatform
from app.utils.sqids import Sqid

# ─── Publish (CI-only, POST /updates/publish) ──────────────────────────────────
# `ManifestLaunchAsset`/`ManifestAsset` use the camelCase field names of the
# retired Expo Updates protocol v1 wire format (`contentType`/`fileExtension`)
# because `AppUpdate.launch_asset`/`.assets` (models.py) store the publish
# payload verbatim in that casing — `build-ota-payload.js`'s publish payload is
# unaffected by which read protocol serves it, so these stay camelCase even
# though the v1 read path that originally required this casing is gone. The v2
# read path (`protocol.py`'s `build_update_manifest`) re-keys these dicts to
# snake_case for the new client.


class ManifestAsset(BaseSchema):
    """One non-launch asset entry in a publish payload's `assets[]`."""

    key: str
    contentType: str
    url: str
    hash: str
    fileExtension: str


class ManifestLaunchAsset(BaseSchema):
    """A publish payload's `launchAsset` — the JS bundle itself."""

    key: str
    contentType: str
    url: str
    hash: str


class PublishUpdateRequest(BaseSchema):
    """Body `ota.yml` posts after uploading a bundle + assets to S3."""

    runtimeVersion: str
    channel: UpdateChannel
    platform: UpdatePlatform
    launchAsset: ManifestLaunchAsset
    assets: list[ManifestAsset]


class PublishUpdateResponse(BaseSchema):
    """The newly-inserted row's identifiers — a direct in-request INSERT (see
    `routes.py`), so both are known at response time.
    """

    id: Sqid
    updateUuid: str


# ─── Manifest protocol v2 (GET /updates/v2/manifest) ───────────────────────────
# Our own client, our own wire contract — plain snake_case like every other schema
# in this codebase (no `rename="camel"`), unlike the v1 structs above which mirror
# the foreign `expo-updates` spec verbatim. Signed as one flat JSON body (see
# `protocol.py`'s `manifest_v2_response`), not a `multipart/mixed` envelope — there
# is exactly one part, so the v1 protocol's multipart wrapping bought nothing here.


class UpdateAsset(BaseSchema):
    key: str
    content_type: str
    url: str
    hash: str
    """sha256, base64url — unchanged from today's `build-ota-payload.js`."""
    file_extension: str | None = None


class UpdateManifest(BaseSchema):
    update_uuid: str
    created_at: str
    runtime_version: str
    launch_asset: UpdateAsset
    assets: list[UpdateAsset]


class ManifestResponse(BaseSchema):
    status: Literal["update_available", "no_update", "rollback"]
    manifest: UpdateManifest | None = None
    rollback_created_at: str | None = None


class ClientEventRequest(BaseSchema):
    """Body the Swift OTA client (`UpdatesManager.swift`) posts on download
    failure, verify failure, apply, and rollback — the direct fix for "no
    useful signal": these become visible in server logs instead of only
    discoverable via a support ticket or a device in hand. Log-only, no
    dedicated table — this is an observability signal, not a record that
    needs to be queried back.
    """

    event: Literal["download_failed", "verify_failed", "applied", "rolled_back"]
    runtime_version: str
    update_uuid: str | None = None
    detail: str | None = None
