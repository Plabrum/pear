from __future__ import annotations

import base64
import json
import re
from collections.abc import AsyncGenerator

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from litestar.di import Provide
from litestar.testing import AsyncTestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.factory import create_app
from app.platform.updates.enums import RolloutStatus, UpdateChannel, UpdatePlatform
from app.platform.updates.models import AppUpdate, NativeBuildFingerprint

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.

_RUNTIME_VERSION = "1.0.0-fingerprint-abc123"
_HEADERS = {
    "expo-runtime-version": _RUNTIME_VERSION,
    "expo-platform": "ios",
    "expo-channel-name": "production",
    "expo-protocol-version": "1",
}


def _rsa_keypair() -> tuple[str, str]:
    """Return a fresh (private_pem, public_pem) RSA-2048 keypair."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@pytest.fixture
async def updates_client(db_session: AsyncSession) -> AsyncGenerator[AsyncTestClient]:
    """Real app hitting `/updates/manifest` + `/updates/publish`, with `transaction`
    pinned to the savepoint `db_session` — `app_updates` has no RLS (see
    `models.py`), so seeding/reading rows needs no actor or system-mode setup.
    """
    app = create_app(dependencies_overrides={"transaction": Provide(lambda: db_session, sync_to_thread=False)})
    async with AsyncTestClient(app=app) as client:
        yield client


def _parse_multipart_json(response) -> tuple[str, dict, str | None, bytes]:
    """Pull `(part_name, json_body, expo-signature part header, raw json bytes)`
    out of the `multipart/mixed` body this route hand-assembles (see
    `app.platform.updates.multipart.encode_multipart_mixed`).
    """
    content_type = response.headers["content-type"]
    boundary = content_type.split("boundary=")[1]
    raw = response.content
    # Between the opening `--<boundary>\r\n` and the closing `\r\n--<boundary>--`.
    part = raw.split(f"--{boundary}".encode())[1].strip(b"\r\n-")
    header_block, _, json_block = part.partition(b"\r\n\r\n")
    header_text = header_block.decode()
    name_match = re.search(r'name="(\w+)"', header_text)
    sig_match = re.search(r"expo-signature: (.+)", header_text)
    return (
        name_match.group(1) if name_match else "",
        json.loads(json_block),
        sig_match.group(1).strip() if sig_match else None,
        json_block,
    )


async def test_manifest_current_update_returns_no_update_directive(
    updates_client: AsyncTestClient, db_session: AsyncSession
) -> None:
    row = AppUpdate(
        runtime_version=_RUNTIME_VERSION,
        channel=UpdateChannel.PRODUCTION,
        platform=UpdatePlatform.IOS,
        launch_asset={"key": "abc", "contentType": "application/javascript", "url": "https://cdn/abc", "hash": "h"},
        assets=[],
        rollout=RolloutStatus.LIVE,
    )
    db_session.add(row)
    await db_session.flush()

    response = await updates_client.get(
        "/updates/manifest",
        headers={**_HEADERS, "expo-current-update-id": str(row.update_uuid)},
    )

    assert response.status_code == 200
    assert response.headers["expo-protocol-version"] == "1"
    part_name, body, _, _ = _parse_multipart_json(response)
    assert part_name == "directive"
    assert body == {"type": "noUpdateAvailable"}


async def test_manifest_rolled_back_returns_rollback_directive(
    updates_client: AsyncTestClient, db_session: AsyncSession
) -> None:
    row = AppUpdate(
        runtime_version=_RUNTIME_VERSION,
        channel=UpdateChannel.PRODUCTION,
        platform=UpdatePlatform.IOS,
        launch_asset={"key": "abc", "contentType": "application/javascript", "url": "https://cdn/abc", "hash": "h"},
        assets=[],
        rollout=RolloutStatus.ROLLED_BACK,
    )
    db_session.add(row)
    await db_session.flush()

    response = await updates_client.get("/updates/manifest", headers=_HEADERS)

    assert response.status_code == 200
    part_name, body, _, _ = _parse_multipart_json(response)
    assert part_name == "directive"
    assert body["type"] == "rollBackToEmbedded"
    assert body["parameters"]["createdAt"] == row.created_at.isoformat()


async def test_manifest_normal_case_returns_signed_manifest(
    updates_client: AsyncTestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_pem, public_pem = _rsa_keypair()
    monkeypatch.setattr(config, "UPDATES_SIGNING_PRIVATE_KEY", private_pem)

    row = AppUpdate(
        runtime_version=_RUNTIME_VERSION,
        channel=UpdateChannel.PRODUCTION,
        platform=UpdatePlatform.IOS,
        launch_asset={
            "key": "bundle-key",
            "contentType": "application/javascript",
            "url": "https://cdn.example.com/bundle.js",
            "hash": "bundle-hash",
        },
        assets=[
            {
                "key": "asset-key",
                "contentType": "image/png",
                "url": "https://cdn.example.com/asset.png",
                "hash": "asset-hash",
                "fileExtension": ".png",
            }
        ],
        rollout=RolloutStatus.LIVE,
    )
    db_session.add(row)
    await db_session.flush()

    response = await updates_client.get("/updates/manifest", headers=_HEADERS)

    assert response.status_code == 200
    part_name, manifest, signature_header, body_bytes = _parse_multipart_json(response)
    assert part_name == "manifest"
    assert manifest["id"] == str(row.update_uuid)
    assert manifest["runtimeVersion"] == _RUNTIME_VERSION
    assert manifest["launchAsset"]["url"] == "https://cdn.example.com/bundle.js"
    assert manifest["assets"][0]["fileExtension"] == ".png"

    # The `expo-signature` part header carries `sig="<base64>", keyid="main"` —
    # verify it against the public half of the injected keypair.
    assert signature_header is not None
    assert 'keyid="main"' in signature_header
    sig_b64 = signature_header.split('sig="')[1].split('"')[0]
    public_key = serialization.load_pem_public_key(public_pem.encode())
    assert isinstance(public_key, rsa.RSAPublicKey)
    public_key.verify(
        base64.b64decode(sig_b64),
        body_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


_PUBLISH_BODY = {
    "runtimeVersion": _RUNTIME_VERSION,
    "channel": "production",
    "platform": "ios",
    "launchAsset": {
        "key": "bundle-key",
        "contentType": "application/javascript",
        "url": "https://cdn.example.com/bundle.js",
        "hash": "bundle-hash",
    },
    "assets": [
        {
            "key": "asset-key",
            "contentType": "image/png",
            "url": "https://cdn.example.com/asset.png",
            "hash": "asset-hash",
            "fileExtension": ".png",
        }
    ],
}


async def test_publish_rejects_missing_token(updates_client: AsyncTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")
    response = await updates_client.post("/updates/publish", json=_PUBLISH_BODY)
    assert response.status_code == 401


async def test_publish_rejects_wrong_token(updates_client: AsyncTestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")
    response = await updates_client.post(
        "/updates/publish", json=_PUBLISH_BODY, headers={"authorization": "Bearer wrong-token"}
    )
    assert response.status_code == 401


async def test_publish_rejects_when_no_token_configured(
    updates_client: AsyncTestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An unset `UPDATES_PUBLISH_TOKEN` must fail closed, not accept an empty bearer."""
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "")
    response = await updates_client.post("/updates/publish", json=_PUBLISH_BODY, headers={"authorization": "Bearer "})
    assert response.status_code == 401


async def test_publish_inserts_app_update_row(
    updates_client: AsyncTestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")

    response = await updates_client.post(
        "/updates/publish", json=_PUBLISH_BODY, headers={"authorization": "Bearer the-real-token"}
    )

    assert response.status_code == 201
    body = response.json()

    row = (
        await db_session.execute(
            select(AppUpdate).where(
                AppUpdate.runtime_version == _RUNTIME_VERSION,
                AppUpdate.channel == UpdateChannel.PRODUCTION,
                AppUpdate.platform == UpdatePlatform.IOS,
            )
        )
    ).scalar_one()
    assert body["updateUuid"] == str(row.update_uuid)
    assert row.rollout == RolloutStatus.LIVE
    assert row.launch_asset["url"] == "https://cdn.example.com/bundle.js"
    assert row.assets[0]["fileExtension"] == ".png"


# ─── Native build fingerprint (POST guarded, GET unauthenticated) ──────────────


async def test_set_fingerprint_rejects_missing_token(
    updates_client: AsyncTestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")
    response = await updates_client.post(
        "/updates/native-build-fingerprint", json={"platform": "ios", "fingerprint": "abc123"}
    )
    assert response.status_code == 401


async def test_set_fingerprint_rejects_wrong_token(
    updates_client: AsyncTestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")
    response = await updates_client.post(
        "/updates/native-build-fingerprint",
        json={"platform": "ios", "fingerprint": "abc123"},
        headers={"authorization": "Bearer wrong-token"},
    )
    assert response.status_code == 401


async def test_set_fingerprint_rejects_when_no_token_configured(
    updates_client: AsyncTestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "")
    response = await updates_client.post(
        "/updates/native-build-fingerprint",
        json={"platform": "ios", "fingerprint": "abc123"},
        headers={"authorization": "Bearer "},
    )
    assert response.status_code == 401


async def test_set_fingerprint_inserts_row(
    updates_client: AsyncTestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")

    response = await updates_client.post(
        "/updates/native-build-fingerprint",
        json={"platform": "ios", "fingerprint": "abc123"},
        headers={"authorization": "Bearer the-real-token"},
    )

    assert response.status_code == 201
    assert response.json() == {"platform": "ios", "fingerprint": "abc123"}

    row = (
        await db_session.execute(
            select(NativeBuildFingerprint).where(NativeBuildFingerprint.platform == UpdatePlatform.IOS)
        )
    ).scalar_one()
    assert row.fingerprint == "abc123"


async def test_set_fingerprint_upsert_overwrites_not_duplicates(
    updates_client: AsyncTestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_PUBLISH_TOKEN", "the-real-token")
    headers = {"authorization": "Bearer the-real-token"}

    await updates_client.post(
        "/updates/native-build-fingerprint", json={"platform": "ios", "fingerprint": "first"}, headers=headers
    )
    response = await updates_client.post(
        "/updates/native-build-fingerprint", json={"platform": "ios", "fingerprint": "second"}, headers=headers
    )

    assert response.status_code == 201
    assert response.json()["fingerprint"] == "second"

    rows = (
        (
            await db_session.execute(
                select(NativeBuildFingerprint).where(NativeBuildFingerprint.platform == UpdatePlatform.IOS)
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].fingerprint == "second"


async def test_get_fingerprint_no_row_returns_none(updates_client: AsyncTestClient) -> None:
    response = await updates_client.get("/updates/native-build-fingerprint", params={"platform": "ios"})
    assert response.status_code == 200
    assert response.json() == {"platform": "ios", "fingerprint": None}


async def test_get_fingerprint_with_row_is_unauthenticated(
    updates_client: AsyncTestClient, db_session: AsyncSession
) -> None:
    db_session.add(NativeBuildFingerprint(platform=UpdatePlatform.IOS, fingerprint="xyz789"))
    await db_session.flush()

    response = await updates_client.get("/updates/native-build-fingerprint", params={"platform": "ios"})

    assert response.status_code == 200
    assert response.json() == {"platform": "ios", "fingerprint": "xyz789"}
