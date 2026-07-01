from __future__ import annotations

from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class DaterState(State[UserRole, Profile]):
    value = UserRole.DATER
    transitions = [
        # a dater switches into winger mode ("just winging") — they keep their
        # dating_profile, it is simply hidden from feeds while role == WINGER.
        Transition(to=UserRole.WINGER, roles={Role.DATER}),
    ]


class WingerState(State[UserRole, Profile]):
    value = UserRole.WINGER
    transitions = [
        # a winger starts / resumes dating — their dating_profile reappears.
        Transition(to=UserRole.DATER, roles={Role.WINGER}),
    ]


user_role_machine = StateMachine[UserRole, Profile](
    enum_type=UserRole,
    states={
        UserRole.DATER: DaterState,
        UserRole.WINGER: WingerState,
    },
)
