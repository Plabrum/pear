from __future__ import annotations

from app.domain.dating_profiles.enums import DatingStatus
from app.domain.dating_profiles.models import DatingProfile
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class OpenState(State[DatingStatus, DatingProfile]):
    value = DatingStatus.OPEN
    transitions = [
        # the dater pauses dating (takes a break)
        Transition(to=DatingStatus.BREAK, roles={Role.DATER}),
    ]


class BreakState(State[DatingStatus, DatingProfile]):
    value = DatingStatus.BREAK
    transitions = [
        # the dater resumes dating
        Transition(to=DatingStatus.OPEN, roles={Role.DATER}),
    ]


dating_status_machine = StateMachine[DatingStatus, DatingProfile](
    enum_type=DatingStatus,
    states={
        DatingStatus.OPEN: OpenState,
        DatingStatus.BREAK: BreakState,
    },
)
