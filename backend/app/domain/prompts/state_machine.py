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
