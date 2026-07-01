from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.platform.state_machine.exceptions import InvalidTransitionError
from app.platform.state_machine.machine import STATE_MACHINE_REGISTRY, StateMachineService
from app.platform.state_machine.models import StateTransitionLog
from app.platform.state_machine.roles import Actor, Role
from tests.fixtures.ids import fake_id
from tests.fixtures.sample_domain.models import SampleStatus
from tests.fixtures.sample_domain.state_machine import sample_machine


class FakeWidget:
    __tablename__ = "sample_widgets"

    def __init__(self, state: SampleStatus = SampleStatus.DRAFT) -> None:
        self.id = fake_id()
        self.state = state


class FakeActor:
    def __init__(self, role: Role) -> None:
        self.id = fake_id()
        self.role = role


@pytest.fixture
def session() -> MagicMock:
    s = MagicMock()
    s.flush = AsyncMock()
    return s


@pytest.fixture
def service(session: MagicMock) -> StateMachineService:
    return StateMachineService(transaction=session)


async def test_legal_transition_advances_and_logs(service: StateMachineService, session: MagicMock) -> None:
    widget = FakeWidget(state=SampleStatus.DRAFT)
    actor = FakeActor(role=Role.DATER)

    await service.transition(
        sample_machine,
        widget,
        SampleStatus.ACTIVE,
        actor=cast(Actor, actor),
        context={"reason": "ready"},
    )

    assert widget.state == SampleStatus.ACTIVE
    logs = [c.args[0] for c in session.add.call_args_list if isinstance(c.args[0], StateTransitionLog)]
    assert len(logs) == 1
    log = logs[0]
    assert log.object_type == "sample_widgets"
    assert log.object_id == widget.id
    assert log.from_state == SampleStatus.DRAFT.value
    assert log.to_state == SampleStatus.ACTIVE.value
    assert log.actor_id == actor.id
    assert log.context == {"reason": "ready"}


async def test_illegal_transition_raises(service: StateMachineService) -> None:
    # ACTIVE is terminal — there is no ACTIVE -> DRAFT edge.
    widget = FakeWidget(state=SampleStatus.ACTIVE)
    actor = FakeActor(role=Role.DATER)

    with pytest.raises(InvalidTransitionError):
        await service.transition(sample_machine, widget, SampleStatus.DRAFT, actor=cast(Actor, actor))


async def test_wrong_role_rejected(service: StateMachineService) -> None:
    # DRAFT -> ACTIVE is dater-only; a winger may not perform it.
    widget = FakeWidget(state=SampleStatus.DRAFT)
    actor = FakeActor(role=Role.WINGER)

    with pytest.raises(InvalidTransitionError):
        await service.transition(sample_machine, widget, SampleStatus.ACTIVE, actor=cast(Actor, actor))


async def test_system_transition_rejects_role_only_edge(service: StateMachineService) -> None:
    # DRAFT -> ACTIVE requires the DATER role; the SYSTEM actor cannot take it.
    widget = FakeWidget(state=SampleStatus.DRAFT)

    with pytest.raises(InvalidTransitionError):
        await service.system_transition(sample_machine, widget, SampleStatus.ACTIVE)


def test_allowed_transitions_reflect_role() -> None:
    widget = FakeWidget(state=SampleStatus.DRAFT)
    dater = cast(Actor, FakeActor(role=Role.DATER))
    winger = cast(Actor, FakeActor(role=Role.WINGER))
    svc = StateMachineService(transaction=MagicMock())

    assert svc.allowed_transitions(sample_machine, widget, dater) == frozenset({SampleStatus.ACTIVE})
    assert svc.allowed_transitions(sample_machine, widget, winger) == frozenset()


def test_machine_registered() -> None:
    assert STATE_MACHINE_REGISTRY.get(SampleStatus) is sample_machine
