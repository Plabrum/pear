from __future__ import annotations

from unittest.mock import MagicMock

from app.config import TestConfig
from app.platform.media.client import (
    LocalMediaClient,
    PresignedUpload,
    S3Client,
    build_media_client,
)
from app.platform.media.deps import provide_media_client

# `asyncio_mode = "auto"` runs async tests without a marker.


# ── Media client: LocalMediaClient ───────────────────────────────────────────


async def test_local_presign_upload_is_well_formed() -> None:
    media = LocalMediaClient(TestConfig())
    key = "owner-1/photo.jpg"
    result = await media.presign_upload(key, content_type="image/jpeg")

    assert isinstance(result, PresignedUpload)
    assert result.key == key
    assert result.upload_url.startswith("http")
    # The key is embedded in the PUT target so a client uploads to the right object.
    assert key in result.upload_url


async def test_local_presign_download_is_well_formed_and_carries_key() -> None:
    media = LocalMediaClient(TestConfig())
    url = await media.presign_download("owner-1/photo.jpg")
    assert url.startswith("http")
    assert "owner-1/photo.jpg" in url


def test_local_public_url_is_stable_no_presign() -> None:
    media = LocalMediaClient(TestConfig())
    # The public URL is deterministic (no signature/expiry query); two calls return
    # the identical URL.
    key = "u1/a.webp"
    assert media.public_url(key) == media.public_url(key)
    assert media.public_url(key).endswith(key)


async def test_local_delete_records_key() -> None:
    media = LocalMediaClient(TestConfig())
    await media.delete("owner-1/gone.jpg")
    assert "owner-1/gone.jpg" in media.deleted


# ── Media client: S3Client (no network — only URL assembly is exercised) ─────


def test_s3_public_url_uses_configured_base() -> None:
    cfg = TestConfig()
    cfg.S3_PUBLIC_BASE_URL = "https://cdn.pear.example"
    client = S3Client(cfg)
    assert client.public_url("u/a.webp") == "https://cdn.pear.example/u/a.webp"


def test_s3_public_url_falls_back_to_bucket_endpoint() -> None:
    cfg = TestConfig()
    cfg.S3_PUBLIC_BASE_URL = ""
    cfg.S3_MEDIA_BUCKET = "pear-media"
    cfg.AWS_REGION = "us-east-1"
    client = S3Client(cfg)
    assert client.public_url("k.jpg") == "https://pear-media.s3.us-east-1.amazonaws.com/k.jpg"


# ── Client selection / DI ────────────────────────────────────────────────────


def test_media_client_is_local_in_testing() -> None:
    # Sanity: the ENV switch picks the fake (no AWS) in the test config.
    assert isinstance(build_media_client(TestConfig()), LocalMediaClient)


def test_media_dep_uses_active_request_config() -> None:
    # provide_media_client reads the request's active config; assert it returns a
    # LocalMediaClient when that config is the (testing) one.
    request = MagicMock()
    request.app.state.config = TestConfig()
    assert isinstance(provide_media_client(request), LocalMediaClient)
