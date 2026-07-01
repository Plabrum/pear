from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.config import TestConfig
from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
)
from app.domain.photos.storage import (
    build_avatar_key,
    build_photo_key,
    ext_from_filename,
    presign_avatar_upload,
    presign_photo_upload,
)
from app.domain.profiles.queries import (
    fetch_own_dating_profile,
    fetch_profile,
    fetch_public_profile,
)
from app.domain.profiles.transformers import (
    bundle_to_public_profile,
    dating_profile_to_own,
    row_to_profile,
)
from app.platform.media.client import (
    LocalMediaClient,
    PresignedUpload,
    S3Client,
    build_media_client,
)
from app.platform.media.deps import provide_media_client
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` runs async tests without a marker.


# ── Media client: LocalMediaClient ───────────────────────────────────────────────


async def test_local_presign_upload_is_well_formed() -> None:
    media = local_media()
    key = "owner-1/photo.jpg"
    result = await media.presign_upload(key, content_type="image/jpeg")

    assert isinstance(result, PresignedUpload)
    assert result.key == key
    assert result.upload_url.startswith("http")
    # The key is embedded in the PUT target so a client uploads to the right object.
    assert key in result.upload_url


async def test_local_presign_download_is_well_formed_and_carries_key() -> None:
    media = local_media()
    url = await media.presign_download("owner-1/photo.jpg")
    assert url.startswith("http")
    assert "owner-1/photo.jpg" in url


def test_local_public_url_is_stable_no_presign() -> None:
    media = local_media()
    # The public URL is deterministic (no signature/expiry query) — avatars are
    # public-read, so two calls return the identical URL.
    key = "avatars/u1/a.jpg"
    assert media.public_url(key) == media.public_url(key)
    assert media.public_url(key).endswith(key)


async def test_local_delete_records_key() -> None:
    media = local_media()
    await media.delete("owner-1/gone.jpg")
    assert "owner-1/gone.jpg" in media.deleted


# ── Media client: S3Client (no network — only URL assembly is exercised) ─────────


def test_s3_public_url_uses_configured_base() -> None:
    cfg = TestConfig()
    cfg.S3_PUBLIC_BASE_URL = "https://cdn.pear.example"
    client = S3Client(cfg)
    assert client.public_url("avatars/u/a.jpg") == "https://cdn.pear.example/avatars/u/a.jpg"


def test_s3_public_url_falls_back_to_bucket_endpoint() -> None:
    cfg = TestConfig()
    cfg.S3_PUBLIC_BASE_URL = ""
    cfg.S3_MEDIA_BUCKET = "pear-media"
    cfg.AWS_REGION = "us-east-1"
    client = S3Client(cfg)
    assert client.public_url("k.jpg") == "https://pear-media.s3.us-east-1.amazonaws.com/k.jpg"


# ── Key builders (own-folder write intent) ───────────────────────────────────────


def test_build_photo_key_is_rooted_in_owner_folder() -> None:
    owner = uuid4()
    key = build_photo_key(owner, "vacation.PNG")
    assert key.startswith(f"{owner}/")
    assert key.endswith(".png")  # extension lowercased + allowlisted


def test_build_avatar_key_is_rooted_in_avatars_user_folder() -> None:
    user_id = uuid4()
    key = build_avatar_key(user_id, "me.jpeg")
    assert key.startswith(f"avatars/{user_id}/")
    assert key.endswith(".jpeg")


def test_ext_from_filename_allowlist_and_default() -> None:
    assert ext_from_filename("a.jpg") == "jpg"
    assert ext_from_filename("a.HEIC") == "heic"
    # A non-image / hostile suffix falls back to jpg (never smuggled into the key).
    assert ext_from_filename("a.exe") == "jpg"
    assert ext_from_filename("noext") == "jpg"


# ── Photo upload-url (presign + own-folder authorization) ─────────────────────────


async def test_photo_upload_url_returns_url_and_owner_rooted_key(graph: DomainGraph, db_session) -> None:
    media = local_media()
    result = await presign_photo_upload(
        db_session,
        caller_id=graph.dater_a.id,
        dating_profile_id=graph.dating_profile_a.id,
        filename="p.jpg",
        content_type="image/jpeg",
        media=media,
    )

    assert result.uploadUrl.startswith("http")
    # Key is rooted in the OWNER's (dater_a's) folder — own-folder write.
    assert result.key.startswith(f"{graph.dater_a.id}/")
    assert result.key in result.uploadUrl


async def test_photo_upload_url_winger_writes_into_dater_folder(graph: DomainGraph, db_session) -> None:
    # The active wingperson uploads a suggestion: the key is still rooted in the
    # DATER's folder, never the winger's.
    result = await presign_photo_upload(
        db_session,
        caller_id=graph.winger.id,
        dating_profile_id=graph.dating_profile_a.id,
        filename="s.jpg",
        content_type="image/jpeg",
        media=local_media(),
    )
    assert result.key.startswith(f"{graph.dater_a.id}/")
    assert not result.key.startswith(f"{graph.winger.id}/")


async def test_photo_upload_url_denied_for_non_wingperson(graph: DomainGraph, db_session) -> None:
    with pytest.raises(NotDaterOrWingpersonError):
        await presign_photo_upload(
            db_session,
            caller_id=graph.dater_c.id,
            dating_profile_id=graph.dating_profile_a.id,
            filename="x.jpg",
            content_type="image/jpeg",
            media=local_media(),
        )


async def test_photo_upload_url_missing_profile(graph: DomainGraph, db_session) -> None:
    with pytest.raises(DatingProfileNotFoundError):
        await presign_photo_upload(
            db_session,
            caller_id=graph.dater_a.id,
            dating_profile_id=uuid4(),
            filename="x.jpg",
            content_type="image/jpeg",
            media=local_media(),
        )


# ── Avatar upload-url (own avatar, public-read) ───────────────────────────────────


async def test_avatar_upload_url_rooted_in_caller_folder_with_public_url(
    graph: DomainGraph,
) -> None:
    media = local_media()
    result = await presign_avatar_upload(
        caller_id=graph.dater_a.id,
        filename="me.jpg",
        content_type="image/jpeg",
        media=media,
    )

    assert result.uploadUrl.startswith("http")
    assert result.key.startswith(f"avatars/{graph.dater_a.id}/")
    # publicUrl is the stable public-read URL for the same key (avatars are public).
    assert result.publicUrl == media.public_url(result.key)
    assert result.publicUrl.endswith(result.key)


# ── Read visibility gating (approved-public read) ─────────────────────────────────


async def test_own_dating_profile_presigns_all_photos(graph: DomainGraph, db_session) -> None:
    # The OWNER sees pending AND approved photos; both get a presigned storageUrl.
    media = local_media()
    bundle = await fetch_own_dating_profile(db_session, graph.dater_a.id)
    assert bundle is not None
    base, photos, prompts = bundle
    dto = await dating_profile_to_own(base, photos, prompts, media)

    assert len(dto.photos) == 2  # 1 approved + 1 pending
    for p in dto.photos:
        assert p.storageUrl.startswith("http")


async def test_public_profile_only_serves_approved_photos(graph: DomainGraph, db_session) -> None:
    # Give dater_a (whose graph has 1 approved + 1 pending photo) a public read and
    # assert the PENDING photo is filtered out — only the approved key is presigned.
    media = local_media()
    bundle = await fetch_public_profile(db_session, graph.dater_a.id)
    assert bundle is not None
    profile, base, photos, prompts = bundle

    # The query already dropped the pending photo (approved-only).
    assert all(photo.approved_at is not None for photo, _ in photos)

    dto = await bundle_to_public_profile(profile, base, photos, prompts, media)
    assert dto.datingProfile is not None
    # Exactly the one approved photo is visible, with a presigned URL.
    assert len(dto.datingProfile.photos) == 1
    assert dto.datingProfile.photos[0].approvedAt is not None
    assert dto.datingProfile.photos[0].storageUrl.startswith("http")


async def test_avatar_resolves_to_public_url_on_own_profile(graph: DomainGraph, db_session) -> None:
    # Set an avatar KEY on the profile; the own-profile read resolves it to a public
    # URL (not a presigned one), since avatars are public-read.
    media = local_media()
    row = await fetch_profile(db_session, graph.dater_a.id)
    assert row is not None
    row.avatar_url = f"avatars/{graph.dater_a.id}/a.jpg"
    await db_session.flush()

    dto = row_to_profile(row, media)
    assert dto.avatarUrl is not None
    assert dto.avatarUrl == media.public_url(f"avatars/{graph.dater_a.id}/a.jpg")
    # Public URL — no presign query string.
    assert "?" not in dto.avatarUrl


def test_media_client_is_local_in_testing() -> None:
    # Sanity: the ENV switch picks the fake (no AWS) in the test config.
    assert isinstance(build_media_client(TestConfig()), LocalMediaClient)


def test_media_dep_uses_active_request_config() -> None:
    # provide_media_client reads the request's active config; assert it returns a
    # LocalMediaClient when that config is the (testing) one.

    request = MagicMock()
    request.app.state.config = TestConfig()
    assert isinstance(provide_media_client(request), LocalMediaClient)
