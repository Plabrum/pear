"""Approval state machine for `prompt_responses`.

The doc (docs/migration/05-domains.md) models the prompt-response approval flow as
a state machine: PENDING -> APPROVED / PENDING -> REJECTED, owner-gated. The Phase-3
`PromptResponse` model stores this as two booleans (`is_approved` / `is_rejected`)
rather than a single status column, so we cannot drive it through the platform
`StateMachineService` directly — that service reads/writes a single `state`
attribute and reads `__tablename__` / `id` for the audit log.

`_ResponseStateAdapter` bridges the gap: it projects the booleans onto
`ApprovalState` and back. The platform service sets `adapter.state = to`, which the
adapter's setter writes onto the underlying `PromptResponse` booleans. The audit
log + STATE_CHANGED event are still emitted (keyed by the real row's table + id),
so the approval is a first-class, logged transition — never a raw column assignment
in the action.

Topology:
    PENDING --(dater)--> APPROVED   # the profile owner approves a comment
    PENDING --(dater)--> REJECTED   # the profile owner rejects a comment
    APPROVED / REJECTED             # terminal

Role-gating: only a DATER may approve/reject (the profile owner). Per-object
ownership ("this dater owns *this* prompt's profile") is enforced in the action's
`is_available`, not on the transition (the transition only knows the caller role).
"""

from __future__ import annotations

from typing import Any

from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.models import PromptResponse
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class _ResponseStateAdapter:
    """Projects a `PromptResponse`'s approval booleans onto `ApprovalState`.

    Satisfies the structural contract the platform `StateMachineService` needs
    (`state` get/set, `id`, `__tablename__`). Setting `.state` writes the booleans
    back onto the wrapped response so a transition mutates the real row.
    """

    def __init__(self, response: PromptResponse) -> None:
        self._response = response
        self.id = response.id

    @property
    def __tablename__(self) -> str:  # noqa: N807 - mirrors ORM attribute name
        return PromptResponse.__tablename__

    @property
    def state(self) -> ApprovalState:
        if self._response.is_approved:
            return ApprovalState.APPROVED
        if self._response.is_rejected:
            return ApprovalState.REJECTED
        return ApprovalState.PENDING

    @state.setter
    def state(self, value: ApprovalState) -> None:
        self._response.is_approved = value is ApprovalState.APPROVED
        self._response.is_rejected = value is ApprovalState.REJECTED


class PendingState(State[ApprovalState, Any]):
    value = ApprovalState.PENDING
    transitions = [
        Transition(to=ApprovalState.APPROVED, roles={Role.DATER}),
        Transition(to=ApprovalState.REJECTED, roles={Role.DATER}),
    ]


class ApprovedState(State[ApprovalState, Any]):
    value = ApprovalState.APPROVED
    transitions: list[Transition[Any]] = []  # terminal


class RejectedState(State[ApprovalState, Any]):
    value = ApprovalState.REJECTED
    transitions: list[Transition[Any]] = []  # terminal


prompt_response_approval_machine = StateMachine[ApprovalState, Any](
    enum_type=ApprovalState,
    states={
        ApprovalState.PENDING: PendingState,
        ApprovalState.APPROVED: ApprovedState,
        ApprovalState.REJECTED: RejectedState,
    },
)


def adapt(response: PromptResponse) -> _ResponseStateAdapter:
    """Wrap a `PromptResponse` so the platform state-machine service can drive it."""
    return _ResponseStateAdapter(response)
