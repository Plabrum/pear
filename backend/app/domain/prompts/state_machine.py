from __future__ import annotations

from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.models import PromptResponse
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class PendingState(State[ApprovalState, PromptResponse]):
    value = ApprovalState.PENDING
    transitions = [
        Transition(to=ApprovalState.APPROVED, roles={Role.DATER}),
        Transition(to=ApprovalState.REJECTED, roles={Role.DATER}),
    ]


class ApprovedState(State[ApprovalState, PromptResponse]):
    value = ApprovalState.APPROVED
    transitions: list[Transition[ApprovalState]] = []  # terminal


class RejectedState(State[ApprovalState, PromptResponse]):
    value = ApprovalState.REJECTED
    transitions: list[Transition[ApprovalState]] = []  # terminal


prompt_response_approval_machine = StateMachine[ApprovalState, PromptResponse](
    enum_type=ApprovalState,
    states={
        ApprovalState.PENDING: PendingState,
        ApprovalState.APPROVED: ApprovedState,
        ApprovalState.REJECTED: RejectedState,
    },
)
