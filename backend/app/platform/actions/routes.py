from litestar import Router, get, post

from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.registry import ActionRegistry
from app.platform.actions.schemas import (
    ActionExecutionResponse,
    ActionListResponse,
    build_action_union,
)
from app.platform.auth.guards import requires_session
from app.utils.discovery import discover_and_import
from app.utils.sqids import Sqid

# Import every domain's `actions.py` so the action classes register themselves
# into the singleton ActionRegistry before we build the request union below.
discover_and_import(["actions.py", "actions/**/*.py"], base_path="app/domain")


@get("/{action_group:str}")
async def list_actions(
    action_group: ActionGroupType,
    action_registry: ActionRegistry,
    action_deps: ActionDeps,
) -> ActionListResponse:
    """List available top-level actions for a group (no object context)."""
    action_group_instance = action_registry.get_class(action_group)
    available_actions = action_group_instance.get_available_actions(action_deps)

    return ActionListResponse(actions=available_actions)


@get("/{action_group:str}/{object_id:str}")
async def list_object_actions(
    action_group: ActionGroupType,
    object_id: Sqid,
    action_registry: ActionRegistry,
    action_deps: ActionDeps,
) -> ActionListResponse:
    """List available actions for a specific object within a group."""
    action_group_instance = action_registry.get_class(action_group)
    obj = await action_group_instance.get_object(object_id, action_deps.transaction)
    available_actions = action_group_instance.get_available_actions(action_deps, obj)

    return ActionListResponse(actions=available_actions)


# Build the discriminated Action union from all registered actions. Frozen at
# import time, after discovery has populated the registry.
Action = build_action_union(ActionRegistry())


@post("/{action_group:str}")
async def execute_action(
    action_group: ActionGroupType,
    data: Action,  # type: ignore [valid-type]
    action_registry: ActionRegistry,
    action_deps: ActionDeps,
) -> ActionExecutionResponse:
    action_group_instance = action_registry.get_class(action_group)
    return await action_group_instance.trigger(
        data=data,
        deps=action_deps,
        object_id=None,
    )


@post("/{action_group:str}/{object_id:str}")
async def execute_object_action(
    action_group: ActionGroupType,
    object_id: Sqid,
    data: Action,  # type: ignore [valid-type]
    action_registry: ActionRegistry,
    action_deps: ActionDeps,
) -> ActionExecutionResponse:
    action_group_instance = action_registry.get_class(action_group)
    return await action_group_instance.trigger(
        data=data,
        deps=action_deps,
        object_id=object_id,
    )


action_router = Router(
    path="/actions",
    route_handlers=[
        list_actions,
        list_object_actions,
        execute_action,
        execute_object_action,
    ],
    tags=["actions"],
    guards=[requires_session],
)
