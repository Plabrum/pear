from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.models import ProfilePhoto
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class PendingState(State[PhotoApprovalState, ProfilePhoto]):
    value = PhotoApprovalState.PENDING
    transitions = [
        Transition(to=PhotoApprovalState.APPROVED, roles={Role.DATER}),
        Transition(to=PhotoApprovalState.REJECTED, roles={Role.DATER}),
    ]


class ApprovedState(State[PhotoApprovalState, ProfilePhoto]):
    value = PhotoApprovalState.APPROVED
    transitions: list[Transition[Any]] = []  # terminal

    async def on_enter(
        self,
        service: Any,
        obj: ProfilePhoto,
        from_state: PhotoApprovalState,
        context: dict[str, Any] | None,
    ) -> None:
        obj.approved_at = datetime.now(tz=UTC)
        obj.rejected_at = None


class RejectedState(State[PhotoApprovalState, ProfilePhoto]):
    value = PhotoApprovalState.REJECTED
    transitions: list[Transition[Any]] = []  # terminal

    async def on_enter(
        self,
        service: Any,
        obj: ProfilePhoto,
        from_state: PhotoApprovalState,
        context: dict[str, Any] | None,
    ) -> None:
        obj.rejected_at = datetime.now(tz=UTC)
        obj.approved_at = None
        # Storage deletion (the rejected photo's S3 object) happens in the
        # RejectPhoto action, which has the `media` client — the state machine only
        # owns the timestamp columns.


photo_approval_machine = StateMachine[PhotoApprovalState, ProfilePhoto](
    enum_type=PhotoApprovalState,
    states={
        PhotoApprovalState.PENDING: PendingState,
        PhotoApprovalState.APPROVED: ApprovedState,
        PhotoApprovalState.REJECTED: RejectedState,
    },
)
