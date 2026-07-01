from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from litestar.exceptions import PermissionDeniedException

from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.registry import ActionRegistry
from app.platform.actions.schemas import build_action_union
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.sample_domain.actions import ActivateWidget, sample_widget_actions
from tests.fixtures.sample_domain.models import SampleStatus


class FakeWidget:
    __tablename__ = "sample_widgets"

    def __init__(self, state: SampleStatus = SampleStatus.DRAFT) -> None:
        self.id = uuid4()
        self.state = state
        self.name = "test"


def _make_deps(*, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps with a real StateMachineService (mock session) and a test user."""
    session = MagicMock()
    session.flush = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=uuid4(), role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=MagicMock(),
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


def _activate_request():
    """Build the discriminated request struct that maps to ActivateWidget.

    The generated struct wraps the action's data param: field `data: EmptyActionData`.
    """
    registry = ActionRegistry()
    build_action_union(registry)
    struct_cls = next(s for s, a in registry._struct_to_action.items() if a is ActivateWidget)
    return struct_cls(data=EmptyActionData())


def test_sample_action_is_registered() -> None:
    registry = ActionRegistry()
    assert registry.is_registered(ActionGroupType.SAMPLE_WIDGET_ACTIONS)
    group = registry.get_class(ActionGroupType.SAMPLE_WIDGET_ACTIONS)
    assert group is sample_widget_actions
    combined_key = f"{ActionGroupType.SAMPLE_WIDGET_ACTIONS.value}__activate"
    assert combined_key in registry._flat_registry
    assert registry._flat_registry[combined_key] is ActivateWidget


def test_is_available_gates_on_draft_state() -> None:
    deps = _make_deps()
    assert ActivateWidget.is_available(FakeWidget(SampleStatus.DRAFT), deps) is True
    assert ActivateWidget.is_available(FakeWidget(SampleStatus.ACTIVE), deps) is False


def test_available_actions_listed_only_for_draft() -> None:
    deps = _make_deps()
    draft_actions = sample_widget_actions.get_available_actions(deps, FakeWidget(SampleStatus.DRAFT))
    active_actions = sample_widget_actions.get_available_actions(deps, FakeWidget(SampleStatus.ACTIVE))

    assert [a.action for a in draft_actions] == [f"{ActionGroupType.SAMPLE_WIDGET_ACTIONS.value}__activate"]
    assert active_actions == []
    # target_state surfaced for the client.
    assert draft_actions[0].target_state == SampleStatus.ACTIVE.value


async def test_trigger_executes_when_available() -> None:
    deps = _make_deps(role=Role.DATER)
    widget = FakeWidget(SampleStatus.DRAFT)
    sample_widget_actions.get_object = AsyncMock(return_value=widget)  # type: ignore[method-assign]

    result = await sample_widget_actions.trigger(data=_activate_request(), deps=deps, object_id=widget.id)

    assert widget.state == SampleStatus.ACTIVE
    assert result.message == "Widget activated"
    assert "sample_widgets" in result.invalidate_queries


async def test_trigger_blocked_when_not_available() -> None:
    deps = _make_deps(role=Role.DATER)
    widget = FakeWidget(SampleStatus.ACTIVE)  # already active -> is_available False
    sample_widget_actions.get_object = AsyncMock(return_value=widget)  # type: ignore[method-assign]

    with pytest.raises(PermissionDeniedException):
        await sample_widget_actions.trigger(data=_activate_request(), deps=deps, object_id=widget.id)
    assert widget.state == SampleStatus.ACTIVE


def test_sample_action_in_openapi_union() -> None:
    """The sample action's request struct is part of the discriminated Action union."""
    registry = ActionRegistry()
    build_action_union(registry)
    assert any(a is ActivateWidget for a in registry._struct_to_action.values())
