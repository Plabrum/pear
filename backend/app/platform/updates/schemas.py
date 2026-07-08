from __future__ import annotations

from typing import Any, Literal

from app.platform.base.schemas import BaseSchema
from app.platform.updates.enums import UpdateChannel, UpdatePlatform
from app.utils.sqids import Sqid

# Expo Updates protocol v1 — https://docs.expo.dev/technical-specs/expo-updates-1/
# Field names/casing below match the spec exactly (camelCase on the wire), not the
# project's usual snake_case-in/camelCase-out convention — this is a foreign wire
# contract the `expo-updates` native client parses directly, not an Orval-generated
# shape, so there is no rename layer to lean on.


class ManifestAsset(BaseSchema):
    """One non-launch asset entry in the manifest's `assets[]`."""

    key: str
    contentType: str
    url: str
    hash: str
    fileExtension: str


class ManifestLaunchAsset(BaseSchema):
    """The manifest's `launchAsset` — the JS bundle itself."""

    key: str
    contentType: str
    url: str
    hash: str


class Manifest(BaseSchema):
    """The signed body of a manifest response (the `manifest` multipart part)."""

    id: str
    createdAt: str
    runtimeVersion: str
    launchAsset: ManifestLaunchAsset
    assets: list[ManifestAsset]
    metadata: dict[str, Any] = {}
    extra: dict[str, Any] = {}


class NoUpdateAvailableDirective(BaseSchema):
    """Told to the client when its `expo-current-update-id` is already current."""

    type: Literal["noUpdateAvailable"] = "noUpdateAvailable"


class RollBackDirectiveParameters(BaseSchema):
    createdAt: str


class RollBackDirective(BaseSchema):
    """Told to the client when the latest row for this tuple has been killed."""

    parameters: RollBackDirectiveParameters
    type: Literal["rollBackToEmbedded"] = "rollBackToEmbedded"


# ─── Publish (CI-only, POST /updates/publish) ──────────────────────────────────
# Reuses `ManifestLaunchAsset`/`ManifestAsset` verbatim — the publish payload and
# the manifest the route later serves share one shape, so there's no separate
# "input" struct to keep in sync with the wire format above.


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


# ─── Native build fingerprint (Xcode Cloud write-back, CI read) ────────────────


class SetNativeBuildFingerprintRequest(BaseSchema):
    """Body `ci_post_xcodebuild.sh` posts after a successful native archive."""

    platform: UpdatePlatform
    fingerprint: str


class NativeBuildFingerprintResponse(BaseSchema):
    platform: UpdatePlatform
    fingerprint: str | None
    """`None` when no native build has ever been recorded for this platform —
    `ota.yml`'s fingerprint guardrail must treat that the same as a hard mismatch.
    """


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
