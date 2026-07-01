from __future__ import annotations

import io
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TestConfig
from app.platform.auth.principal import User
from app.platform.media.enums import MediaState
from app.platform.media.exceptions import MediaNotFoundError
from app.platform.media.models import Media
from app.platform.media.routes import MediaController
from app.platform.media.schemas import PresignedUploadRequest
from app.platform.media.service import MediaService
from app.platform.media.tasks import process_image
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import ActingAs, DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _png_bytes(*, mode: str = "RGB", size: tuple[int, int] = (8, 8)) -> bytes:
    img = Image.new(mode, size, color=(120, 30, 200) if mode == "RGB" else (120, 30, 200, 255))
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


def _jpeg_bytes(size: tuple[int, int] = (8, 8)) -> bytes:
    img = Image.new("RGB", size, color=(10, 200, 10))
    out = io.BytesIO()
    img.save(out, format="JPEG")
    return out.getvalue()


async def _seed_media(session: AsyncSession, owner_id) -> Media:
    media = Media(
        owner_id=owner_id,
        file_key=f"{owner_id}/orig.jpg",
        processed_key=None,
        mime_type="image/jpeg",
        file_name="orig.jpg",
    )
    session.add(media)
    await session.flush()
    return media


# ── process_image: PNG/JPEG -> WebP, reaches READY ───────────────────────────


@pytest.mark.parametrize("data_fn", [_jpeg_bytes, _png_bytes])
async def test_process_image_reencodes_to_webp_and_reaches_ready(
    graph: DomainGraph, db_session: AsyncSession, data_fn
) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)

    # A LocalMediaClient pre-loaded (in-memory) with the original upload bytes.
    client = local_media()
    await client.upload(media.file_key, data_fn(), content_type="image/jpeg")

    ctx = {"config": TestConfig(), "media_client": client}
    await process_image(ctx, transaction=db_session, media_id=str(media.id))

    refreshed = (await db_session.execute(select(Media).where(Media.id == media.id))).scalar_one()
    assert refreshed.state is MediaState.READY
    assert refreshed.processed_key is not None
    assert refreshed.processed_key.endswith(".webp")

    # The processed object exists and decodes as a real WebP image.
    webp_bytes, content_type = client.store[refreshed.processed_key]
    assert content_type == "image/webp"
    with Image.open(io.BytesIO(webp_bytes)) as img:
        assert img.format == "WEBP"


async def test_process_image_missing_bytes_marks_failed(graph: DomainGraph, db_session: AsyncSession) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)

    # Empty store -> download raises MediaError -> task swallows and marks FAILED.
    client = local_media()
    ctx = {"config": TestConfig(), "media_client": client}
    await process_image(ctx, transaction=db_session, media_id=str(media.id))

    refreshed = (await db_session.execute(select(Media).where(Media.id == media.id))).scalar_one()
    assert refreshed.state is MediaState.FAILED
    assert refreshed.processed_key is None


# ── RLS: owner + active wingperson manage; unrelated user denied ──────────────


async def test_media_rls_owner_sees_own_row(graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    async with acting_as(graph.dater_a.id) as s:
        rows = set((await s.execute(select(Media.id))).scalars().all())
        assert media.id in rows


async def test_media_rls_active_wingperson_sees_row(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    # winger is an ACTIVE wingperson for dater_a in the seeded graph.
    media = await _seed_media(db_session, graph.dater_a.id)
    async with acting_as(graph.winger.id) as s:
        rows = set((await s.execute(select(Media.id))).scalars().all())
        assert media.id in rows


async def test_media_rls_unrelated_user_denied(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    await _seed_media(db_session, graph.dater_a.id)
    # dater_c is neither the owner nor an active wingperson of dater_a.
    async with acting_as(graph.dater_c.id) as s:
        count = (await s.execute(select(func.count()).select_from(Media))).scalar_one()
        assert count == 0


async def test_media_rls_owner_can_update_and_delete(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    async with acting_as(graph.dater_a.id) as s:
        row = (await s.execute(select(Media).where(Media.id == media.id))).scalar_one()
        row.file_name = "renamed.jpg"
        await s.flush()
        await s.delete(row)
        await s.flush()
        # The owner's own row is gone (the graph's other dater_a media are untouched).
        gone = (await s.execute(select(func.count()).select_from(Media).where(Media.id == media.id))).scalar_one()
        assert gone == 0


async def test_media_rls_active_wingperson_can_insert_on_behalf(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    async with acting_as(graph.winger.id) as s:
        s.add(
            Media(
                owner_id=graph.dater_a.id,
                file_key=f"{graph.dater_a.id}/w.jpg",
                mime_type="image/jpeg",
                file_name="w.jpg",
            )
        )
        await s.flush()  # WITH CHECK passes for the active wingperson


# ── system-mode resolve (the photos domain's authorized cross-user read) ─────


async def test_resolve_urls_system_presigns_under_system_mode(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    client = local_media()
    # dater_b is matched to dater_a but media RLS would NOT let them SELECT the row.
    async with acting_as(graph.dater_b.id) as s:
        # Sanity: ordinary scope cannot see it.
        assert (await s.execute(select(func.count()).select_from(Media))).scalar_one() == 0
        service = MediaService(s, client)
        urls = await service.resolve_urls_system([media.id])
        assert media.id in urls
        assert urls[media.id].startswith("http")
        # System mode was restored: the row is invisible again.
        assert (await s.execute(select(func.count()).select_from(Media))).scalar_one() == 0


# ── Routes: upload-url / uploaded / delete happy paths ───────────────────────


def _user(uid, *, role: Role = Role.DATER) -> User:
    return User(id=uid, role=role)


# Litestar wraps each handler in an HTTPRouteHandler; `.fn` is the raw coroutine
# (taking `self` first). The handlers never touch `self`, so a sentinel suffices.
_SELF = MagicMock()


async def test_route_upload_url_creates_pending_media(graph: DomainGraph, db_session: AsyncSession) -> None:
    client = local_media()
    resp = await MediaController.upload_url.fn(
        _SELF,
        PresignedUploadRequest(fileName="pic.jpg", contentType="image/jpeg"),
        _user(graph.dater_a.id),
        db_session,
        client,
    )
    assert resp.mediaId is not None
    assert resp.uploadUrl.startswith("http")
    assert resp.key.startswith(f"{graph.dater_a.id}/")

    row = (await db_session.execute(select(Media).where(Media.id == resp.mediaId))).scalar_one()
    assert row.state is MediaState.PENDING
    assert row.owner_id == graph.dater_a.id
    assert row.file_key == resp.key


async def test_route_uploaded_enqueues_processing(graph: DomainGraph, db_session: AsyncSession) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    with patch("app.platform.media.routes.dispatch_task", new=AsyncMock()) as dispatched:
        resp = await MediaController.uploaded.fn(_SELF, media.id, MagicMock(), _user(graph.dater_a.id), db_session)
    assert resp.id == media.id
    dispatched.assert_awaited_once()
    # media_id arg is the row id as a string.
    await_args = dispatched.await_args
    assert await_args is not None
    assert await_args.kwargs["media_id"] == str(media.id)


async def test_route_uploaded_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    with patch("app.platform.media.routes.dispatch_task", new=AsyncMock()):
        with pytest.raises(MediaNotFoundError):
            await MediaController.uploaded.fn(_SELF, media.id, MagicMock(), _user(graph.dater_b.id), db_session)


async def test_route_get_one_resolves_url(graph: DomainGraph, db_session: AsyncSession) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    client = local_media()
    resp = await MediaController.get_one.fn(_SELF, media.id, db_session, client)
    assert resp.id == media.id
    # Not READY -> falls back to presigning the original file_key.
    assert resp.url.startswith("http")


async def test_route_delete_removes_file_and_row(graph: DomainGraph, db_session: AsyncSession) -> None:
    media = await _seed_media(db_session, graph.dater_a.id)
    media.processed_key = f"{graph.dater_a.id}/orig.webp"
    await db_session.flush()

    client = local_media()
    await MediaController.delete_one.fn(_SELF, media.id, db_session, client)
    await db_session.flush()  # handler relies on the request tx commit; flush to observe

    assert media.file_key in client.deleted
    assert media.processed_key in client.deleted
    remaining = (
        await db_session.execute(select(func.count()).select_from(Media).where(Media.id == media.id))
    ).scalar_one()
    assert remaining == 0


async def test_route_get_one_missing_raises(graph: DomainGraph, db_session: AsyncSession) -> None:
    client = local_media()
    with pytest.raises(MediaNotFoundError):
        await MediaController.get_one.fn(_SELF, uuid4(), db_session, client)
