"""Photo approval state machine: pending -> approved / pending -> rejected.

The original Supabase schema has no status column for a photo — approval is encoded
by two nullable timestamps (`approved_at`, `rejected_at`). To gate the approve /
reject mutations through the platform `StateMachineService` (per the migration doc's
approval-machine mapping) we surface that timestamp pair as a derived
`PhotoApprovalState` (see `enums.py`).

Topology (owner = the dater who owns the profile; modeled as `Role.DATER`):

    PENDING --(dater)--> APPROVED     # sets approved_at = now()
    PENDING --(dater)--> REJECTED     # sets rejected_at = now() (+ delete storage — Phase 6)
    APPROVED            (terminal)
    REJECTED            (terminal)

so approve/reject are only legal on a PENDING photo, and the dater is the only role
that may perform them. Because `ProfilePhoto` has no real `state` column, this module
attaches a read-only `state` property onto the model: the getter derives the value
from the timestamps; the setter is a no-op because the canonical write happens in the
`State.on_enter` hooks below (which set the underlying `approved_at` / `rejected_at`).
This keeps the action layer honest — it sets `target_state` and calls
`StateMachineService.transition`, never the timestamp columns directly.
"""

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
        # TODO(Phase 6): delete the rejected photo's bytes from object storage.


photo_approval_machine = StateMachine[PhotoApprovalState, ProfilePhoto](
    enum_type=PhotoApprovalState,
    states={
        PhotoApprovalState.PENDING: PendingState,
        PhotoApprovalState.APPROVED: ApprovedState,
        PhotoApprovalState.REJECTED: RejectedState,
    },
)
