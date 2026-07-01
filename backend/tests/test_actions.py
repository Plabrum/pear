from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from litestar.exceptions import PermissionDeniedException
from sqlalchemy.exc import ProgrammingError

from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.registry import ActionRegistry
from app.platform.actions.schemas import build_action_union
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.ids import fake_id
from tests.fixtures.sample_domain.actions import ActivateWidget, sample_widget_actions
from tests.fixtures.sample_domain.models import SampleStatus, SampleWidget


def _widget(state: SampleStatus = SampleStatus.DRAFT) -> SampleWidget:
    """A real SampleWidget built in-memory (no session) for action-gating tests."""
    return SampleWidget(id=fake_id(), state=state, name="test", user_id=fake_id())


def _make_deps(*, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps with a real StateMachineService (mock session) and a test user."""
    session = MagicMock()
    session.flush = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=fake_id(), role=role),
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
    assert ActivateWidget.is_available(_widget(SampleStatus.DRAFT), deps.user, deps) is True
    assert ActivateWidget.is_available(_widget(SampleStatus.ACTIVE), deps.user, deps) is False


def test_available_actions_listed_only_for_draft() -> None:
    deps = _make_deps()
    draft_actions = sample_widget_actions.get_available_actions(deps, _widget(SampleStatus.DRAFT))
    active_actions = sample_widget_actions.get_available_actions(deps, _widget(SampleStatus.ACTIVE))

    assert [a.action for a in draft_actions] == [f"{ActionGroupType.SAMPLE_WIDGET_ACTIONS.value}__activate"]
    assert active_actions == []
    # target_state surfaced for the client.
    assert draft_actions[0].target_state == SampleStatus.ACTIVE.value


async def test_trigger_executes_when_available() -> None:
    deps = _make_deps(role=Role.DATER)
    widget = _widget(SampleStatus.DRAFT)
    sample_widget_actions.get_object = AsyncMock(return_value=widget)  # type: ignore[method-assign]

    result = await sample_widget_actions.trigger(data=_activate_request(), deps=deps, object_id=widget.id)

    assert widget.state == SampleStatus.ACTIVE
    assert result.message == "Widget activated"
    assert "sample_widgets" in result.invalidate_queries


async def test_trigger_blocked_when_not_available() -> None:
    deps = _make_deps(role=Role.DATER)
    widget = _widget(SampleStatus.ACTIVE)  # already active -> is_available False
    sample_widget_actions.get_object = AsyncMock(return_value=widget)  # type: ignore[method-assign]

    with pytest.raises(PermissionDeniedException):
        await sample_widget_actions.trigger(data=_activate_request(), deps=deps, object_id=widget.id)
    assert widget.state == SampleStatus.ACTIVE


async def test_trigger_translates_rls_denial_to_403() -> None:
    """A write rejected by an RLS WITH CHECK policy (SQLSTATE 42501) surfaces as a 403.

    The non-superuser `pear_app` role under FORCE RLS raises `insufficient_privilege`
    when a caller writes outside their scope. The dispatcher must turn that into a
    PermissionDeniedException rather than leaking a 500.
    """
    deps = _make_deps(role=Role.DATER)
    widget = _widget(SampleStatus.DRAFT)
    sample_widget_actions.get_object = AsyncMock(return_value=widget)  # type: ignore[method-assign]

    orig = MagicMock()
    orig.sqlstate = "42501"
    rls_denial = ProgrammingError("INSERT ...", {}, orig)

    with patch.object(ActivateWidget, "execute", AsyncMock(side_effect=rls_denial)):
        with pytest.raises(PermissionDeniedException):
            await sample_widget_actions.trigger(data=_activate_request(), deps=deps, object_id=widget.id)


async def test_trigger_does_not_swallow_non_rls_db_errors() -> None:
    """A DB error that is NOT an RLS denial propagates unchanged (stays a 500)."""
    deps = _make_deps(role=Role.DATER)
    widget = _widget(SampleStatus.DRAFT)
    sample_widget_actions.get_object = AsyncMock(return_value=widget)  # type: ignore[method-assign]

    orig = MagicMock()
    orig.sqlstate = "23505"  # unique_violation — a genuine integrity error, not authz
    other_error = ProgrammingError("INSERT ...", {}, orig)

    with patch.object(ActivateWidget, "execute", AsyncMock(side_effect=other_error)):
        with pytest.raises(ProgrammingError):
            await sample_widget_actions.trigger(data=_activate_request(), deps=deps, object_id=widget.id)


def test_sample_action_in_openapi_union() -> None:
    """The sample action's request struct is part of the discriminated Action union."""
    registry = ActionRegistry()
    build_action_union(registry)
    assert any(a is ActivateWidget for a in registry._struct_to_action.values())
