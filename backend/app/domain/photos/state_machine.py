from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.models import ProfilePhoto
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


def derive_state(photo: ProfilePhoto) -> PhotoApprovalState:
    if photo.rejected_at is not None:
        return PhotoApprovalState.REJECTED
    if photo.approved_at is not None:
        return PhotoApprovalState.APPROVED
    return PhotoApprovalState.PENDING


def _set_state(photo: ProfilePhoto, value: PhotoApprovalState) -> None:
    # No-op: the canonical column writes happen in the State.on_enter hooks. The
    # StateMachineService assigns `obj.state = to` as part of its generic flow; we
    # accept it without mutating columns so the timestamp pair stays the single
    # source of truth.
    return None


# Attach the derived `state` view onto the ORM model so the platform
# StateMachineService (which reads/writes `obj.state`) can drive transitions
# without `profile_photos` carrying a dedicated status column. Callers that need
# the value in typed code use `derive_state(photo)` instead (the dynamic property
# is invisible to the type checker, by design — only the Any-typed machine uses it).
ProfilePhoto.state = property(derive_state, _set_state)  # type: ignore[attr-defined]


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
