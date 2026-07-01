from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.actions import (
    ApprovePhoto,
    CreatePhoto,
    DeletePhoto,
    RejectPhoto,
    ReorderPhoto,
)
from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
    PhotoNotFoundError,
)
from app.domain.photos.models import ProfilePhoto
from app.domain.photos.queries import fetch_own_photos
from app.domain.photos.schemas import CreatePhotoData, ReorderPhotoData
from app.domain.photos.state_machine import derive_state
from app.domain.photos.transformers import photos_to_dtos
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.media.models import Media
from app.platform.media.service import MediaService
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import ActingAs, DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor (push is mocked)."""
    push = MagicMock()
    push.send = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
        realtime=MagicMock(),
        media=local_media(),
    )


async def _get_photo(session: AsyncSession, photo_id) -> ProfilePhoto | None:
    return (await session.execute(select(ProfilePhoto).where(ProfilePhoto.id == photo_id))).scalar_one_or_none()


# ── Reads ──────────────────────────────────────────────────────────────────────


async def test_list_own_photos_ordered_with_suggester(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_own_photos(db_session, graph.dater_a.id)
    # The route resolves every photo's media_id in one batched system-mode pass.
    url_by_media = await MediaService(db_session, local_media()).resolve_urls_system(
        [photo.media_id for photo, _ in rows]
    )
    dtos = photos_to_dtos(rows, url_by_media)

    # graph seeds 1 approved (self) + 1 pending (winger-suggested) photo.
    assert [d.displayOrder for d in dtos] == [0, 1]
    approved, pending = dtos

    assert approved.approvedAt is not None
    assert approved.suggesterId is None
    assert approved.suggester is None
    # storageUrl is now the resolved (presigned) media URL, keyed by media_id.
    assert approved.storageUrl.startswith("http")
    # The approved media is READY, so its processed (WebP) key is the servable one.
    processed_key = graph.approved_media.processed_key
    assert processed_key is not None and processed_key in approved.storageUrl

    assert pending.approvedAt is None
    assert pending.suggesterId == graph.winger.id
    assert pending.suggester is not None
    assert pending.suggester.chosenName == graph.winger.chosen_name
    assert pending.datingProfileId == graph.dating_profile_a.id


async def test_list_own_photos_empty_for_unrelated_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b's profile has no seeded photos.
    assert await fetch_own_photos(db_session, graph.dater_b.id) == []


# ── State derivation ─────────────────────────────────────────────────────────────


async def test_derived_state_reflects_timestamps(graph: DomainGraph, db_session: AsyncSession) -> None:
    assert derive_state(graph.approved_photo) is PhotoApprovalState.APPROVED
    assert derive_state(graph.pending_photo) is PhotoApprovalState.PENDING


# ── Actions: create ──────────────────────────────────────────────────────────────


async def _seed_media(session: AsyncSession, owner_id) -> Media:
    """A PENDING media owned by `owner_id`, flushed for its id."""
    media = Media(
        owner_id=owner_id,
        file_key=f"{owner_id}/new.jpg",
        processed_key=None,
        mime_type="image/jpeg",
        file_name="new.jpg",
    )
    session.add(media)
    await session.flush()
    return media


async def test_create_photo_self_upload_auto_approved(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    media = await _seed_media(db_session, graph.dater_a.id)
    data = CreatePhotoData(
        datingProfileId=graph.dating_profile_a.id,
        mediaId=media.id,
        displayOrder=2,
    )
    result = await CreatePhoto.execute(data, db_session, deps)

    assert result.created_id is not None
    photo = await _get_photo(db_session, result.created_id)
    assert photo is not None
    assert photo.media_id == media.id
    assert photo.suggester_id is None
    assert photo.approved_at is not None  # self-uploads are auto-approved
    # Self-uploads don't notify a wingperson.
    cast(AsyncMock, deps.push.send).assert_not_awaited()


async def test_create_photo_winger_suggestion_pending_and_pushes(graph: DomainGraph, db_session: AsyncSession) -> None:
    # winger is an active wingperson for dater_a; media is owned by the dater.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    media = await _seed_media(db_session, graph.dater_a.id)
    data = CreatePhotoData(
        datingProfileId=graph.dating_profile_a.id,
        mediaId=media.id,
        displayOrder=3,
    )
    result = await CreatePhoto.execute(data, db_session, deps)

    photo = await _get_photo(db_session, result.created_id)
    assert photo is not None
    assert photo.media_id == media.id
    assert photo.suggester_id == graph.winger.id
    assert photo.approved_at is None  # winger suggestions start pending
    # dater_a has no push token seeded -> send is skipped, but the suggester-name
    # lookup ran without error. Assert no crash and pending state.
    assert derive_state(photo) is PhotoApprovalState.PENDING


async def test_create_photo_denied_for_non_wingperson(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is unrelated to dater_a's profile (no active contact).
    deps = _deps(db_session, user_id=graph.dater_c.id)
    data = CreatePhotoData(
        datingProfileId=graph.dating_profile_a.id,
        mediaId=uuid4(),
        displayOrder=9,
    )
    with pytest.raises(NotDaterOrWingpersonError):
        await CreatePhoto.execute(data, db_session, deps)


async def test_create_photo_missing_dating_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreatePhotoData(datingProfileId=uuid4(), mediaId=uuid4(), displayOrder=0)
    with pytest.raises(DatingProfileNotFoundError):
        await CreatePhoto.execute(data, db_session, deps)


# ── Actions: approve / reject (state machine) ────────────────────────────────────


async def test_approve_photo_happy_path(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    photo = graph.pending_photo

    assert ApprovePhoto.is_available(photo, deps) is True
    result = await ApprovePhoto.execute(photo, EmptyActionData(), db_session, deps)

    assert result.message == "Photo approved"
    refreshed = await _get_photo(db_session, photo.id)
    assert refreshed is not None
    assert refreshed.approved_at is not None
    assert derive_state(refreshed) is PhotoApprovalState.APPROVED


async def test_approve_photo_unavailable_when_already_approved(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    # The seeded approved photo is no longer pending -> gate denies.
    assert ApprovePhoto.is_available(graph.approved_photo, deps) is False


async def test_approve_photo_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger (suggester) is not the owning dater; execute raises 404.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    with pytest.raises(PhotoNotFoundError):
        await ApprovePhoto.execute(graph.pending_photo, EmptyActionData(), db_session, deps)


async def test_reject_photo_happy_path(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    photo = graph.pending_photo

    assert RejectPhoto.is_available(photo, deps) is True
    result = await RejectPhoto.execute(photo, EmptyActionData(), db_session, deps)

    assert result.message == "Photo rejected"
    refreshed = await _get_photo(db_session, photo.id)
    assert refreshed is not None
    assert refreshed.rejected_at is not None
    assert refreshed.approved_at is None
    assert derive_state(refreshed) is PhotoApprovalState.REJECTED


# ── Actions: delete ──────────────────────────────────────────────────────────────


async def test_delete_photo_by_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    photo_id = graph.approved_photo.id

    result = await DeletePhoto.execute(graph.approved_photo, EmptyActionData(), db_session, deps)
    assert result.message == "Photo deleted"
    assert await _get_photo(db_session, photo_id) is None


async def test_delete_photo_by_suggester(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger who suggested the pending photo may delete it.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    photo_id = graph.pending_photo.id

    await DeletePhoto.execute(graph.pending_photo, EmptyActionData(), db_session, deps)
    assert await _get_photo(db_session, photo_id) is None


async def test_delete_photo_denied_for_unrelated_user(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_c.id)
    with pytest.raises(PhotoNotFoundError):
        await DeletePhoto.execute(graph.approved_photo, EmptyActionData(), db_session, deps)


# ── Actions: reorder ─────────────────────────────────────────────────────────────


async def test_reorder_photo_by_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = ReorderPhotoData(displayOrder=5)

    result = await ReorderPhoto.execute(graph.approved_photo, data, db_session, deps)
    assert result.message == "Photo reordered"
    refreshed = await _get_photo(db_session, graph.approved_photo.id)
    assert refreshed is not None
    assert refreshed.display_order == 5


async def test_reorder_photo_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_c.id)
    data = ReorderPhotoData(displayOrder=5)
    with pytest.raises(PhotoNotFoundError):
        await ReorderPhoto.execute(graph.pending_photo, data, db_session, deps)


# ── Matched viewer: approved photo URL via system resolve, no direct media row ───


async def test_matched_viewer_resolves_approved_photo_url(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    # dater_b is matched with dater_a but is neither owner nor wingperson of dater_a,
    # so media RLS hides dater_a's media rows from a direct SELECT. The photos read
    # path authorizes the approved photo, then resolves its URL in system mode.
    approved_media_id = graph.approved_photo.media_id
    async with acting_as(graph.dater_b.id) as s:
        # Sanity: dater_b cannot directly read the owner's media row.
        assert (await s.execute(select(func.count()).select_from(Media))).scalar_one() == 0

        service = MediaService(s, local_media())
        urls = await service.resolve_urls_system([approved_media_id])
        assert approved_media_id in urls
        assert urls[approved_media_id].startswith("http")
        # READY media resolves to its processed (WebP) key.
        processed_key = graph.approved_media.processed_key
        assert processed_key is not None and processed_key in urls[approved_media_id]

        # System mode was restored: the media row is invisible again.
        assert (await s.execute(select(func.count()).select_from(Media))).scalar_one() == 0
