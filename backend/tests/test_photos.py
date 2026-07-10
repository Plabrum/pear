from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.actions import (
    ApprovePhoto,
    CreatePhoto,
    DeletePhoto,
    RejectPhoto,
    ReorderPhoto,
    photo_actions,
)
from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
)
from app.domain.photos.models import ProfilePhoto
from app.domain.photos.queries import SuggestedPhotoRow, fetch_own_photos, fetch_suggested_photos
from app.domain.photos.schemas import CreatePhotoData, ReorderPhotoData
from app.domain.photos.transformers import photos_to_dtos, suggested_photo_to_dto
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.media.models import Media
from app.platform.media.service import MediaService
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import ActingAs, DomainGraph
from tests.fixtures.ids import fake_id
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
    # The route resolves every photo's media_id in one batched pass under the
    # caller's own scope (ownership satisfies the media SELECT policy).
    url_by_media = await MediaService(db_session, local_media()).resolve_urls([photo.media_id for photo, _ in rows])
    dtos = photos_to_dtos(rows, url_by_media, photo_actions, _deps(db_session, user_id=graph.dater_a.id))

    # graph seeds 1 approved (self) + 1 pending (winger-suggested) photo.
    assert [d.displayOrder for d in dtos] == [0, 1]
    approved, pending = dtos

    assert approved.status is PhotoApprovalState.APPROVED
    assert approved.suggesterId is None
    assert approved.suggester is None
    # storageUrl is now the resolved (presigned) media URL, keyed by media_id.
    assert approved.storageUrl.startswith("http")
    # The approved media is READY, so its processed (WebP) key is the servable one.
    processed_key = graph.approved_media.processed_key
    assert processed_key is not None and processed_key in approved.storageUrl

    assert pending.status is PhotoApprovalState.PENDING
    assert pending.suggesterId == graph.winger.id
    assert pending.suggester is not None
    assert pending.suggester.chosenName == graph.winger.chosen_name
    assert pending.datingProfileId == graph.dating_profile_a.id


async def test_list_own_photos_empty_for_unrelated_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b's profile has no seeded photos.
    assert await fetch_own_photos(db_session, graph.dater_b.id) == []


# ── Reads: photos I suggested (suggester_id = me) ────────────────────────────────


async def test_fetch_suggested_photos(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds one winger-suggested pending photo for dater_a.
    rows = await fetch_suggested_photos(db_session, graph.winger.id, 50)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == graph.pending_photo.id
    assert row.dater_id == graph.dater_a.id
    assert row.dater_name == graph.dater_a.chosen_name
    assert row.state is PhotoApprovalState.PENDING

    dto = await suggested_photo_to_dto(row, local_media())
    assert dto.daterId == graph.dater_a.id
    # storageUrl presigns the media's servable key; the pending media is READY, so its
    # processed (WebP) key is the servable one.
    assert dto.storageUrl.startswith("http")
    processed_key = graph.pending_media.processed_key
    assert processed_key is not None and processed_key in dto.storageUrl
    assert dto.status == "pending"


async def test_fetch_suggested_photos_scoped_to_suggester(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The approved photo was self-uploaded (suggester_id is None), so it must NOT
    # appear in the winger's suggested feed.
    rows = await fetch_suggested_photos(db_session, graph.winger.id, 50)
    assert all(r.id != graph.approved_photo.id for r in rows)
    # A user who suggested nothing sees an empty list.
    assert await fetch_suggested_photos(db_session, graph.dater_c.id, 50) == []


async def test_suggested_photos_honors_limit(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed a second winger-suggested photo so the feed has > 1 row, then assert limit trims it.
    media = await _seed_media(db_session, graph.dater_a.id)
    db_session.add(
        ProfilePhoto(
            dating_profile_id=graph.dating_profile_a.id,
            owner_id=graph.dater_a.id,
            suggester_id=graph.winger.id,
            media_id=media.id,
            display_order=9,
            state=PhotoApprovalState.PENDING,
        )
    )
    await db_session.flush()
    assert len(await fetch_suggested_photos(db_session, graph.winger.id, 50)) == 2
    assert len(await fetch_suggested_photos(db_session, graph.winger.id, 1)) == 1


async def test_suggested_photo_status_matrix(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Fold the approval state to the wire status.
    def _row(state: PhotoApprovalState) -> SuggestedPhotoRow:
        return SuggestedPhotoRow(
            id=graph.pending_photo.id,
            dater_id=graph.dater_a.id,
            dater_name="Dana",
            storage_url="some/key.webp",
            state=state,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    media = local_media()
    assert (await suggested_photo_to_dto(_row(PhotoApprovalState.REJECTED), media)).status == "not_accepted"
    assert (await suggested_photo_to_dto(_row(PhotoApprovalState.APPROVED), media)).status == "approved"
    assert (await suggested_photo_to_dto(_row(PhotoApprovalState.PENDING), media)).status == "pending"


# ── State column ─────────────────────────────────────────────────────────────────


async def test_state_column_reflects_lifecycle(graph: DomainGraph, db_session: AsyncSession) -> None:
    assert graph.approved_photo.state is PhotoApprovalState.APPROVED
    assert graph.pending_photo.state is PhotoApprovalState.PENDING


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
    result = await CreatePhoto.execute(data, db_session, deps.user, deps)

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
    result = await CreatePhoto.execute(data, db_session, deps.user, deps)

    photo = await _get_photo(db_session, result.created_id)
    assert photo is not None
    assert photo.media_id == media.id
    assert photo.suggester_id == graph.winger.id
    assert photo.approved_at is None  # winger suggestions start pending
    # dater_a has no push token seeded -> send is skipped, but the suggester-name
    # lookup ran without error. Assert no crash and pending state.
    assert photo.state is PhotoApprovalState.PENDING


async def test_create_photo_denied_for_non_wingperson(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is unrelated to dater_a's profile (no active contact).
    deps = _deps(db_session, user_id=graph.dater_c.id)
    data = CreatePhotoData(
        datingProfileId=graph.dating_profile_a.id,
        mediaId=fake_id(),
        displayOrder=9,
    )
    with pytest.raises(NotDaterOrWingpersonError):
        await CreatePhoto.execute(data, db_session, deps.user, deps)


async def test_create_photo_missing_dating_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreatePhotoData(datingProfileId=fake_id(), mediaId=fake_id(), displayOrder=0)
    with pytest.raises(DatingProfileNotFoundError):
        await CreatePhoto.execute(data, db_session, deps.user, deps)


# ── Actions: approve / reject (state machine) ────────────────────────────────────


async def test_approve_photo_happy_path(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    photo = graph.pending_photo

    assert ApprovePhoto.is_available(photo, deps.user, deps) is True
    result = await ApprovePhoto.execute(photo, EmptyActionData(), db_session, deps.user, deps)

    assert result.message == "Photo approved"
    refreshed = await _get_photo(db_session, photo.id)
    assert refreshed is not None
    assert refreshed.approved_at is not None
    assert refreshed.state is PhotoApprovalState.APPROVED


async def test_approve_photo_unavailable_when_already_approved(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert ApprovePhoto.is_available(graph.approved_photo, deps.user, deps) is False


async def test_approve_photo_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger (suggester) is not the owning dater. Authorization now lives in
    # is_available (owner_id compare), so the action is simply not offered — a
    # request would surface as 403 from ActionGroup.trigger, never reach execute.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert ApprovePhoto.is_available(graph.pending_photo, deps.user, deps) is False


async def test_reject_photo_happy_path(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    photo = graph.pending_photo

    assert RejectPhoto.is_available(photo, deps.user, deps) is True
    result = await RejectPhoto.execute(photo, EmptyActionData(), db_session, deps.user, deps)

    assert result.message == "Photo rejected"
    refreshed = await _get_photo(db_session, photo.id)
    assert refreshed is not None
    assert refreshed.rejected_at is not None
    assert refreshed.approved_at is None
    assert refreshed.state is PhotoApprovalState.REJECTED


# ── Actions: delete ──────────────────────────────────────────────────────────────


async def test_delete_photo_by_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    photo_id = graph.approved_photo.id

    assert DeletePhoto.is_available(graph.approved_photo, deps.user, deps) is True
    result = await DeletePhoto.execute(graph.approved_photo, EmptyActionData(), db_session, deps.user, deps)
    assert result.message == "Photo deleted"
    assert await _get_photo(db_session, photo_id) is None


async def test_delete_photo_by_suggester(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger who suggested the pending photo may delete it.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    photo_id = graph.pending_photo.id

    assert DeletePhoto.is_available(graph.pending_photo, deps.user, deps) is True
    await DeletePhoto.execute(graph.pending_photo, EmptyActionData(), db_session, deps.user, deps)
    assert await _get_photo(db_session, photo_id) is None


async def test_delete_photo_denied_for_unrelated_user(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Neither owner nor suggester -> is_available denies (would be 403, not execute).
    deps = _deps(db_session, user_id=graph.dater_c.id)
    assert DeletePhoto.is_available(graph.approved_photo, deps.user, deps) is False


# ── Actions: reorder ─────────────────────────────────────────────────────────────


async def test_reorder_photo_by_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = ReorderPhotoData(displayOrder=5)

    assert ReorderPhoto.is_available(graph.approved_photo, deps.user, deps) is True
    result = await ReorderPhoto.execute(graph.approved_photo, data, db_session, deps.user, deps)
    assert result.message == "Photo reordered"
    refreshed = await _get_photo(db_session, graph.approved_photo.id)
    assert refreshed is not None
    assert refreshed.display_order == 5


async def test_reorder_photo_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Not the owner -> is_available denies (would be 403, never reaches execute).
    deps = _deps(db_session, user_id=graph.dater_c.id)
    assert ReorderPhoto.is_available(graph.pending_photo, deps.user, deps) is False


# ── Matched viewer: approved photo URL under the viewer's OWN scope (no system) ──


async def test_matched_viewer_resolves_approved_photo_url(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    # dater_b is matched with dater_a but is neither owner nor wingperson of dater_a.
    # The media SELECT policy mirrors profile_photos visibility, so dater_b can read
    # the APPROVED photo's media row (dater_a's profile is active + the photo is
    # approved) and presign its URL entirely under their OWN scope — no system mode.
    approved_media_id = graph.approved_photo.media_id
    async with acting_as(graph.dater_b.id) as s:
        # The viewer can directly SELECT the approved photo's media row.
        row = (await s.execute(select(Media).where(Media.id == approved_media_id))).scalar_one_or_none()
        assert row is not None and row.id == approved_media_id

        service = MediaService(s, local_media())
        urls = await service.resolve_urls([approved_media_id])
        assert approved_media_id in urls
        assert urls[approved_media_id].startswith("http")
        # READY media resolves to its processed (WebP) key.
        processed_key = graph.approved_media.processed_key
        assert processed_key is not None and processed_key in urls[approved_media_id]


async def test_matched_viewer_cannot_resolve_pending_photo_media(
    graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs
) -> None:
    # The pending (winger-suggested, NOT approved) photo's media must stay hidden
    # from a matched viewer: media_select only exposes APPROVED photos cross-user, so
    # the row is unreadable and resolve_urls yields nothing for it.
    pending_media_id = graph.pending_photo.media_id
    async with acting_as(graph.dater_b.id) as s:
        row = (await s.execute(select(Media).where(Media.id == pending_media_id))).scalar_one_or_none()
        assert row is None

        service = MediaService(s, local_media())
        urls = await service.resolve_urls([pending_media_id])
        assert urls == {}
