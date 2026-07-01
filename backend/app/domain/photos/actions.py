from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
    PhotoNotFoundError,
)
from app.domain.photos.models import ProfilePhoto
from app.domain.photos.queries import (
    fetch_dater_push_and_suggester_name,
    fetch_dating_profile_owner,
    is_active_wingperson,
)
from app.domain.photos.schemas import CreatePhotoData, ReorderPhotoData
from app.domain.photos.state_machine import derive_state, photo_approval_machine
from app.platform.actions.base import (
    BaseObjectAction,
    BaseTopLevelAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse


async def _photo_owner_id(transaction: AsyncSession, photo: ProfilePhoto) -> UUID | None:
    """The dater user_id that owns the photo's dating profile (or None)."""
    return await fetch_dating_profile_owner(transaction, photo.dating_profile_id)


# ── Action group ───────────────────────────────────────────────────────────────

photo_actions = action_group_factory(
    ActionGroupType.PHOTO_ACTIONS,
    default_invalidation="photos",
    model_type=ProfilePhoto,
)


# ── POST /photos — create photo metadata ────────────────────────────────────────


@photo_actions
class CreatePhoto(BaseTopLevelAction[CreatePhotoData]):
    action_key = "create"  # type: ignore[assignment]
    label = "Add Photo"
    icon = ActionIcon.ADD

    @classmethod
    async def execute(
        cls,
        data: CreatePhotoData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await fetch_dating_profile_owner(transaction, data.datingProfileId)
        if owner_id is None:
            raise DatingProfileNotFoundError()

        is_owner = owner_id == deps.user.id
        if not is_owner and not await is_active_wingperson(transaction, owner_id, deps.user.id):
            raise NotDaterOrWingpersonError()

        photo = ProfilePhoto(
            dating_profile_id=data.datingProfileId,
            storage_url=data.storageUrl,
            display_order=data.displayOrder,
            suggester_id=None if is_owner else deps.user.id,
            # Self-uploads are auto-approved; winger suggestions start pending.
            approved_at=datetime.now(tz=UTC) if is_owner else None,
        )
        transaction.add(photo)
        await transaction.flush()

        if not is_owner:
            dater_token, suggester_name = await fetch_dater_push_and_suggester_name(transaction, owner_id, deps.user.id)
            if dater_token:
                await deps.push.send(
                    dater_token,
                    "New photo suggestion 📸",
                    f"{suggester_name or 'Your wingperson'} suggested a photo for your profile.",
                )

        return ActionExecutionResponse(
            message="Photo added",
            invalidate_queries=["photos"],
            created_id=photo.id,
        )


# ── POST /photos/{id}/approve ────────────────────────────────────────────────────


@photo_actions
class ApprovePhoto(BaseObjectAction[ProfilePhoto, EmptyActionData]):
    action_key = "approve"  # type: ignore[assignment]
    label = "Approve Photo"
    icon = ActionIcon.CHECK
    target_state = PhotoApprovalState.APPROVED

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        # Owner (dater) only, and only while the photo is still pending. Ownership
        # is verified against the dating profile in execute (no synchronous query
        # available here); the pending precondition is derivable from the state.
        return derive_state(obj) is PhotoApprovalState.PENDING

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await _photo_owner_id(transaction, obj)
        if owner_id != deps.user.id:
            # 404 when the owner-scoped lookup matched no rows for this caller.
            raise PhotoNotFoundError()

        await deps.state_machine_service.transition(
            photo_approval_machine,
            obj,
            PhotoApprovalState.APPROVED,
            actor=deps.user,
        )
        await transaction.flush()
        return ActionExecutionResponse(
            message="Photo approved",
            invalidate_queries=["photos"],
        )


# ── POST /photos/{id}/reject ─────────────────────────────────────────────────────


@photo_actions
class RejectPhoto(BaseObjectAction[ProfilePhoto, EmptyActionData]):
    action_key = "reject"  # type: ignore[assignment]
    label = "Reject Photo"
    icon = ActionIcon.X
    target_state = PhotoApprovalState.REJECTED

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        return derive_state(obj) is PhotoApprovalState.PENDING

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await _photo_owner_id(transaction, obj)
        if owner_id != deps.user.id:
            raise PhotoNotFoundError()

        # The machine's RejectedState.on_enter sets rejected_at. We never assign the
        # timestamp column directly.
        # Capture the S3 key before the transition so we can delete the bytes after.
        storage_key = obj.storage_url
        await deps.state_machine_service.transition(
            photo_approval_machine,
            obj,
            PhotoApprovalState.REJECTED,
            actor=deps.user,
        )
        await transaction.flush()
        # The rejection ROW stays (it feeds the winger-activity rejection feed), but
        # the image bytes are unwanted — delete the S3 object. Log-and-swallow: a
        # failed delete leaks one object, never a broken DB reference. `media` is
        # always injected on the request path; the None-guard only covers unit tests
        # that build ActionDeps without it.
        if deps.media is not None:
            await deps.media.delete(storage_key)
        return ActionExecutionResponse(
            message="Photo rejected",
            invalidate_queries=["photos"],
        )


# ── DELETE /photos/{id} ──────────────────────────────────────────────────────────


@photo_actions
class DeletePhoto(BaseObjectAction[ProfilePhoto, EmptyActionData]):
    action_key = "delete"  # type: ignore[assignment]
    label = "Delete Photo"
    icon = ActionIcon.TRASH
    confirmation_message = "Delete this photo?"

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        # The suggester may always delete their own suggestion; the dater-owner
        # check is data-dependent and verified in execute.
        return True

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await _photo_owner_id(transaction, obj)
        # Dater (owner) OR the wingperson who suggested it may delete the photo.
        if owner_id != deps.user.id and obj.suggester_id != deps.user.id:
            raise PhotoNotFoundError()

        storage_key = obj.storage_url
        await transaction.delete(obj)
        await transaction.flush()
        # Remove the S3 object after the row is gone.
        # Log-and-swallow inside `media.delete`: a leaked object is harmless. `media`
        # is always injected on the request path; the None-guard only covers unit
        # tests that build ActionDeps without it.
        if deps.media is not None:
            await deps.media.delete(storage_key)
        return ActionExecutionResponse(
            message="Photo deleted",
            invalidate_queries=["photos"],
        )


# ── PATCH /photos/{id}/reorder ───────────────────────────────────────────────────


@photo_actions
class ReorderPhoto(BaseObjectAction[ProfilePhoto, ReorderPhotoData]):
    action_key = "reorder"  # type: ignore[assignment]
    label = "Reorder Photo"
    icon = ActionIcon.EDIT
    is_hidden = True  # mechanical drag-reorder, not a surfaced menu action

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: ReorderPhotoData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await _photo_owner_id(transaction, obj)
        if owner_id != deps.user.id:
            raise PhotoNotFoundError()

        obj.display_order = data.displayOrder
        await transaction.flush()
        return ActionExecutionResponse(
            message="Photo reordered",
            invalidate_queries=["photos"],
        )
