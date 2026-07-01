"""Throwaway sample state machine — proves the StateMachine abstraction.

Topology:
    DRAFT  --(dater)-->  ACTIVE      # legal
    ACTIVE               (terminal)  # no outbound edges -> ACTIVE->DRAFT is illegal

`StateMachineService.transition(..., to=ACTIVE)` succeeds from DRAFT for a dater;
transitioning back to DRAFT (or to ACTIVE from ACTIVE) raises
`InvalidTransitionError`. Auto-registers into `STATE_MACHINE_REGISTRY` on
construction. Lives under `tests/fixtures/` so it never ships to prod.
"""

from typing import Any

from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role
from tests.fixtures.sample_domain.models import SampleStatus, SampleWidget


class DraftState(State[SampleStatus, SampleWidget]):
    value = SampleStatus.DRAFT
    transitions = [
        Transition(to=SampleStatus.ACTIVE, roles={Role.DATER}),
    ]


class ActiveState(State[SampleStatus, SampleWidget]):
    value = SampleStatus.ACTIVE
    transitions: list[Transition[Any]] = []  # terminal — no legal outbound edges


sample_machine = StateMachine[SampleStatus, SampleWidget](
    enum_type=SampleStatus,
    states={
        SampleStatus.DRAFT: DraftState,
        SampleStatus.ACTIVE: ActiveState,
    },
)
