from __future__ import annotations

from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class PendingState(State[DecisionState, Decision]):
    value = DecisionState.PENDING
    transitions = [
        # the dater acts on a winger suggestion (or directly likes a pending row)
        Transition(to=DecisionState.APPROVED, roles={Role.DATER}),
        # the dater passes on a suggestion, or a viewer blocks/reports a pending pair
        Transition(to=DecisionState.DECLINED, roles={Role.DATER, Role.WINGER}),
    ]


class ApprovedState(State[DecisionState, Decision]):
    value = DecisionState.APPROVED
    transitions = [
        # blocking/reporting someone you already liked retracts the like
        Transition(to=DecisionState.DECLINED, roles={Role.DATER, Role.WINGER}),
    ]


class DeclinedState(State[DecisionState, Decision]):
    value = DecisionState.DECLINED
    transitions: list[Transition[DecisionState]] = []  # terminal


decision_machine = StateMachine[DecisionState, Decision](
    enum_type=DecisionState,
    states={
        DecisionState.PENDING: PendingState,
        DecisionState.APPROVED: ApprovedState,
        DecisionState.DECLINED: DeclinedState,
    },
)
