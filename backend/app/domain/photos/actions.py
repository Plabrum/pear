from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
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

# ── Action group ───────────────────────────────────────────────────────────────


class PhotoActionKey(StrEnum):
    CREATE = "create"
    APPROVE = "approve"
    REJECT = "reject"
    DELETE = "delete"
    REORDER = "reorder"


photo_actions = action_group_factory(
    ActionGroupType.PHOTO_ACTIONS,
    default_invalidation="photos",
    model_type=ProfilePhoto,
)


# ── POST /photos — create photo metadata ────────────────────────────────────────


@photo_actions
class CreatePhoto(BaseTopLevelAction[CreatePhotoData]):
    action_key: ClassVar[PhotoActionKey] = PhotoActionKey.CREATE
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
            owner_id=owner_id,
            media_id=data.mediaId,
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
    action_key: ClassVar[PhotoActionKey] = PhotoActionKey.APPROVE
    label = "Approve Photo"
    icon = ActionIcon.CHECK
    target_state = PhotoApprovalState.APPROVED

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        # Owner (dater) only, and only while the photo is still pending. Ownership
        # is a flat column compare now that owner_id rides on the row.
        return derive_state(obj) is PhotoApprovalState.PENDING and obj.owner_id == deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
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
    action_key: ClassVar[PhotoActionKey] = PhotoActionKey.REJECT
    label = "Reject Photo"
    icon = ActionIcon.X
    target_state = PhotoApprovalState.REJECTED

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        # Owner (dater) only, only while pending — flat column compare on owner_id.
        return derive_state(obj) is PhotoApprovalState.PENDING and obj.owner_id == deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        # The machine's RejectedState.on_enter sets rejected_at. We never assign the
        # timestamp column directly.
        await deps.state_machine_service.transition(
            photo_approval_machine,
            obj,
            PhotoApprovalState.REJECTED,
            actor=deps.user,
        )
        await transaction.flush()
        # The rejection ROW stays (it feeds the winger-activity rejection feed). The
        # underlying bytes belong to the platform Media row, whose deletion is owned
        # by the media domain (DELETE /media/{id}) — this domain no longer touches storage.
        return ActionExecutionResponse(
            message="Photo rejected",
            invalidate_queries=["photos"],
        )


# ── DELETE /photos/{id} ──────────────────────────────────────────────────────────


@photo_actions
class DeletePhoto(BaseObjectAction[ProfilePhoto, EmptyActionData]):
    action_key: ClassVar[PhotoActionKey] = PhotoActionKey.DELETE
    label = "Delete Photo"
    icon = ActionIcon.TRASH
    confirmation_message = "Delete this photo?"

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        # Dater (owner) OR the wingperson who suggested it may delete the photo —
        # both flat column compares now that owner_id rides on the row.
        return obj.owner_id == deps.user.id or obj.suggester_id == deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await transaction.delete(obj)
        await transaction.flush()
        # Only the photo link is removed here; the platform Media row (the bytes) is
        # deleted via the media domain's DELETE /media/{id}, which owns storage cleanup.
        return ActionExecutionResponse(
            message="Photo deleted",
            invalidate_queries=["photos"],
        )


# ── PATCH /photos/{id}/reorder ───────────────────────────────────────────────────


@photo_actions
class ReorderPhoto(BaseObjectAction[ProfilePhoto, ReorderPhotoData]):
    action_key: ClassVar[PhotoActionKey] = PhotoActionKey.REORDER
    label = "Reorder Photo"
    icon = ActionIcon.EDIT
    is_hidden = True  # mechanical drag-reorder, not a surfaced menu action

    @classmethod
    def is_available(cls, obj: ProfilePhoto, deps: ActionDeps) -> bool:
        # Owner (dater) only — flat column compare on owner_id.
        return obj.owner_id == deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: ProfilePhoto,
        data: ReorderPhotoData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        obj.display_order = data.displayOrder
        await transaction.flush()
        return ActionExecutionResponse(
            message="Photo reordered",
            invalidate_queries=["photos"],
        )
