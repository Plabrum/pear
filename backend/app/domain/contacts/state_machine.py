from __future__ import annotations

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class InvitedState(State[WingpersonStatus, Contact]):
    value = WingpersonStatus.INVITED
    transitions = [
        # winger accepts the invitation
        Transition(to=WingpersonStatus.ACTIVE, roles={Role.WINGER}),
        # winger declines, or the dater cancels the pending invite
        Transition(to=WingpersonStatus.REMOVED, roles={Role.WINGER, Role.DATER}),
    ]


class ActiveState(State[WingpersonStatus, Contact]):
    value = WingpersonStatus.ACTIVE
    transitions = [
        # the dater removes an active wingperson
        Transition(to=WingpersonStatus.REMOVED, roles={Role.DATER}),
    ]


class RemovedState(State[WingpersonStatus, Contact]):
    value = WingpersonStatus.REMOVED
    transitions: list[Transition[WingpersonStatus]] = []  # terminal


contact_machine = StateMachine[WingpersonStatus, Contact](
    enum_type=WingpersonStatus,
    states={
        WingpersonStatus.INVITED: InvitedState,
        WingpersonStatus.ACTIVE: ActiveState,
        WingpersonStatus.REMOVED: RemovedState,
    },
)
