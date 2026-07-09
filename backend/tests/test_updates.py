from __future__ import annotations

import base64
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
from app.platform.updates.models import AppUpdate

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.

_RUNTIME_VERSION = "1.0.0-fingerprint-abc123"


def _rsa_keypair() -> tuple[str, str]:
    """Return a fresh (private_key_b64, public_pem) RSA-2048 keypair — the private
    half base64-encoded, matching how UPDATES_SIGNING_PRIVATE_KEY is stored."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return base64.b64encode(private_pem).decode(), public_pem


@pytest.fixture
async def updates_client(db_session: AsyncSession) -> AsyncGenerator[AsyncTestClient]:
    """Real app hitting `/updates/v2/manifest` + `/updates/publish`, with
    `transaction` pinned to the savepoint `db_session` — `app_updates` has no RLS
    (see `models.py`), so seeding/reading rows needs no actor or system-mode setup.
    """
    app = create_app(dependencies_overrides={"transaction": Provide(lambda: db_session, sync_to_thread=False)})
    async with AsyncTestClient(app=app) as client:
        yield client


def _v2_params(**overrides: str) -> dict[str, str]:
    return {
        "runtime_version": _RUNTIME_VERSION,
        "platform": "ios",
        "channel": "production",
        **overrides,
    }


def _assert_valid_v2_signature(response, public_pem: str) -> None:
    signature_b64 = response.headers.get("x-update-signature")
    assert signature_b64 is not None
    assert response.headers["x-update-signing-key-id"] == "main"
    public_key = serialization.load_pem_public_key(public_pem.encode())
    assert isinstance(public_key, rsa.RSAPublicKey)
    public_key.verify(
        base64.b64decode(signature_b64),
        response.content,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )


async def test_manifest_v2_no_row_returns_no_update(updates_client: AsyncTestClient) -> None:
    response = await updates_client.get("/updates/v2/manifest", params=_v2_params())

    assert response.status_code == 200
    assert response.json() == {"status": "no_update", "manifest": None, "rollback_created_at": None}


async def test_manifest_v2_current_update_returns_no_update(
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
        "/updates/v2/manifest", params=_v2_params(current_update_id=str(row.update_uuid))
    )

    assert response.status_code == 200
    assert response.json()["status"] == "no_update"


async def test_manifest_v2_rolled_back_returns_rollback(
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

    response = await updates_client.get("/updates/v2/manifest", params=_v2_params())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "rollback"
    assert body["rollback_created_at"] == row.created_at.isoformat()


async def test_manifest_v2_normal_case_returns_signed_manifest(
    updates_client: AsyncTestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    private_key_b64, public_pem = _rsa_keypair()
    monkeypatch.setattr(config, "UPDATES_SIGNING_PRIVATE_KEY", private_key_b64)

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

    response = await updates_client.get("/updates/v2/manifest", params=_v2_params())

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "update_available"
    manifest = body["manifest"]
    assert manifest["update_uuid"] == str(row.update_uuid)
    assert manifest["runtime_version"] == _RUNTIME_VERSION
    assert manifest["launch_asset"] == {
        "key": "bundle-key",
        "content_type": "application/javascript",
        "url": "https://cdn.example.com/bundle.js",
        "hash": "bundle-hash",
        "file_extension": None,
    }
    assert manifest["assets"][0] == {
        "key": "asset-key",
        "content_type": "image/png",
        "url": "https://cdn.example.com/asset.png",
        "hash": "asset-hash",
        "file_extension": ".png",
    }
    _assert_valid_v2_signature(response, public_pem)


async def test_manifest_v2_unsigned_when_no_signing_key_configured(
    updates_client: AsyncTestClient, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "UPDATES_SIGNING_PRIVATE_KEY", "")

    response = await updates_client.get("/updates/v2/manifest", params=_v2_params())

    assert response.status_code == 200
    assert "x-update-signature" not in response.headers


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
