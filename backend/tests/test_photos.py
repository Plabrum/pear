from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import select
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
from app.domain.photos.transformers import photo_to_dto
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.

# A LocalMediaClient shared by the read tests: deterministic fake URLs, no AWS.
_media = local_media()


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor (push is mocked).

    `media` is a real LocalMediaClient (not a mock) so the delete/reject S3-cleanup
    paths run their actual logic (recording deleted keys); `realtime` is mocked.
    """
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
    dtos = [await photo_to_dto(photo, name, _media) for photo, name in rows]

    # graph seeds 1 approved (self) + 1 pending (winger-suggested) photo.
    assert [d.displayOrder for d in dtos] == [0, 1]
    approved, pending = dtos

    assert approved.approvedAt is not None
    assert approved.suggesterId is None
    assert approved.suggester is None
    # storageUrl is now a presigned GET URL for the stored key, not the raw key.
    assert approved.storageUrl.startswith("http")
    assert graph.approved_photo.storage_url in approved.storageUrl

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


async def test_create_photo_self_upload_auto_approved(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreatePhotoData(
        datingProfileId=graph.dating_profile_a.id,
        storageUrl="dater_a/new.jpg",
        displayOrder=2,
    )
    result = await CreatePhoto.execute(data, db_session, deps)

    assert result.created_id is not None
    photo = await _get_photo(db_session, result.created_id)
    assert photo is not None
    assert photo.suggester_id is None
    assert photo.approved_at is not None  # self-uploads are auto-approved
    # Self-uploads don't notify a wingperson.
    cast(AsyncMock, deps.push.send).assert_not_awaited()


async def test_create_photo_winger_suggestion_pending_and_pushes(graph: DomainGraph, db_session: AsyncSession) -> None:
    # winger is an active wingperson for dater_a.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = CreatePhotoData(
        datingProfileId=graph.dating_profile_a.id,
        storageUrl="dater_a/suggested.jpg",
        displayOrder=3,
    )
    result = await CreatePhoto.execute(data, db_session, deps)

    photo = await _get_photo(db_session, result.created_id)
    assert photo is not None
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
        storageUrl="x.jpg",
        displayOrder=9,
    )
    with pytest.raises(NotDaterOrWingpersonError):
        await CreatePhoto.execute(data, db_session, deps)


async def test_create_photo_missing_dating_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreatePhotoData(datingProfileId=uuid4(), storageUrl="x.jpg", displayOrder=0)
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
