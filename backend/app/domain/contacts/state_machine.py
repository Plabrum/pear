"""Contacts state machine — the wingperson-invitation lifecycle.

`wingperson_status` IS a state machine; this models it as one so legality lives in
the topology + role gating instead of scattered `if status == …` checks (the
05-domains.md "gate actions on state" payoff).

Topology (states -> outbound edges):

    INVITED --(winger)--> ACTIVE       # accept       (winger only)
    INVITED --(winger)--> REMOVED      # decline      (winger only)
    INVITED --(dater)-->  REMOVED      # cancel-invite (dater)
    ACTIVE  --(dater)-->  REMOVED      # remove active (dater)
    REMOVED               (terminal)

Role-gating lives on each `Transition` (DATER vs WINGER); per-object preconditions
(the *current* status) are the machine's own topology — `is_available()` on each
action narrows further so the client gets a clean "can't accept an active contact".

The Contact model exposes a `state` synonym onto `wingperson_status`, so it drives
the same `StateMachineService` machinery as any `StateMachineMixin` model — actions
call `deps.state_machine_service.transition(contact_machine, obj, target, actor=…)`
and never assign the status column directly.
"""

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
