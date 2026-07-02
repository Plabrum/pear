from __future__ import annotations

import msgspec
from litestar import Response

from app.config import Config
from app.platform.updates.models import AppUpdate
from app.platform.updates.multipart import MultipartPart, encode_multipart_mixed
from app.platform.updates.schemas import (
    Manifest,
    ManifestAsset,
    ManifestLaunchAsset,
    NoUpdateAvailableDirective,
    RollBackDirective,
)
from app.platform.updates.signing import sign_manifest

# The one protocol version this route speaks — pinned so a future `expo-updates`
# major bump that changes the wire contract fails loudly instead of silently
# mis-serving a client.
_PROTOCOL_VERSION = "1"


def _response_headers() -> dict[str, str]:
    return {
        "expo-protocol-version": _PROTOCOL_VERSION,
        "expo-sfv-version": "0",
        "cache-control": "private, no-cache",
    }


def directive_response(
    directive: NoUpdateAvailableDirective | RollBackDirective, config: Config
) -> Response[bytes]:
    body = msgspec.json.encode(directive)
    signature = sign_manifest(body, config)
    extra_headers = {}
    if signature is not None:
        # Same RFC 8941 Structured Field Value format as manifest_response — the
        # client's code-signing certificate requires every multipart/mixed part
        # (directive or manifest) to carry a valid signature, not just manifests.
        extra_headers["expo-signature"] = f'sig="{signature}", keyid="{config.UPDATES_SIGNING_KEY_ID}"'
    part = MultipartPart(name="directive", body=body, extra_headers=extra_headers)
    payload, content_type = encode_multipart_mixed([part])
    return Response(content=payload, media_type=content_type, headers=_response_headers())


def manifest_response(row: AppUpdate, config: Config) -> Response[bytes]:
    manifest = Manifest(
        id=str(row.update_uuid),
        createdAt=row.created_at.isoformat(),
        runtimeVersion=row.runtime_version,
        launchAsset=msgspec.convert(row.launch_asset, ManifestLaunchAsset),
        assets=[msgspec.convert(asset, ManifestAsset) for asset in row.assets],
        metadata={},
        extra={},
    )
    body = msgspec.json.encode(manifest)
    signature = sign_manifest(body, config)
    extra_headers = {}
    if signature is not None:
        # RFC 8941 Structured Field Value — the format `expo-updates` expects for
        # asymmetric (code-signing-certificate) signatures.
        extra_headers["expo-signature"] = f'sig="{signature}", keyid="{config.UPDATES_SIGNING_KEY_ID}"'
    part = MultipartPart(name="manifest", body=body, extra_headers=extra_headers)
    payload, content_type = encode_multipart_mixed([part])
    return Response(content=payload, media_type=content_type, headers=_response_headers())
