from __future__ import annotations

import logging
from abc import ABC
from enum import Enum, StrEnum
from typing import Any, ClassVar
from uuid import UUID

from litestar.exceptions import NotFoundException, PermissionDeniedException
from msgspec import Struct
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.base import ExecutableOption

from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.registry import ActionRegistry
from app.platform.actions.schemas import (
    ActionDTO,
    ActionExecutionResponse,
    DisabledReason,
)
from app.platform.base.models import BaseDBModel

logger = logging.getLogger(__name__)


class EmptyActionData(Struct):
    """Empty struct for actions that don't require any data."""

    pass


class BaseAction[O: BaseDBModel, D: Struct](ABC):
    """Base class for all actions - shared attributes and methods.

    Type parameters:
        O: The database model type this action operates on
        D: The msgspec Struct type for action data/schema

    Use BaseObjectAction for actions that operate on existing objects.
    Use BaseTopLevelAction for actions that don't require an existing object (e.g., create).
    """

    action_key: ClassVar[StrEnum]
    label: ClassVar[str]
    is_bulk_allowed: ClassVar[bool] = False
    priority: ClassVar[int] = 100
    icon: ClassVar[ActionIcon] = ActionIcon.DEFAULT
    confirmation_message: ClassVar[str | None] = None
    should_redirect_to_parent: ClassVar[bool] = False
    is_hidden: ClassVar[bool] = False
    # Set on object actions that move the model to a known state. When set, the
    # action is treated as a state transition and the client derives
    # `is_state_transition` from its presence.
    target_state: ClassVar[Enum | None] = None

    # Model is set by the action group during registration.
    model: ClassVar[type[BaseDBModel] | None] = None

    @classmethod
    def get_label(cls, obj: Any, deps: ActionDeps) -> str:
        """Return a dynamic label for this action. Override for context-dependent labels."""
        return cls.label


class BaseObjectAction[O: BaseDBModel, D: Struct](BaseAction[O, D]):
    """Base class for actions that operate on existing database objects.

    Type parameters:
        O: The database model type this action operates on
        D: The msgspec Struct type for action data/schema

    Subclasses must implement:
        async def execute(cls, obj: O, data: D, transaction: AsyncSession, deps: ActionDeps)
    """

    @classmethod
    def is_available(cls, obj: O, deps: ActionDeps) -> bool:
        return True

    @classmethod
    def is_disabled(cls, obj: O, deps: ActionDeps) -> DisabledReason | None:
        return None

    @classmethod
    async def execute(
        cls,
        obj: O,
        data: D,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        raise NotImplementedError(f"{cls.__name__} must implement execute()")


class BaseTopLevelAction[D: Struct](BaseAction[BaseDBModel, D]):
    """Base class for actions that don't operate on existing objects.

    Type parameters:
        D: The msgspec Struct type for action data/schema

    Subclasses must implement:
        async def execute(cls, data: D, transaction: AsyncSession, deps: ActionDeps)
    """

    @classmethod
    def is_available(cls, deps: ActionDeps) -> bool:
        return True

    @classmethod
    def is_disabled(cls, deps: ActionDeps) -> DisabledReason | None:
        return None

    @classmethod
    async def execute(
        cls,
        data: D,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        raise NotImplementedError(f"{cls.__name__} must implement execute()")


class ActionGroup:
    def __init__(
        self,
        group_type: ActionGroupType,
        action_registry: Any,  # ActionRegistry - forward ref to avoid circular import
        model_type: type[BaseDBModel] | None,
        default_invalidation: str | None = None,
        load_options: list[ExecutableOption] | None = None,
    ) -> None:
        self.group_type = group_type
        self.actions: dict[str, type[BaseAction]] = {}
        self.object_actions: dict[str, type[BaseObjectAction]] = {}
        self.top_level_actions: dict[str, type[BaseTopLevelAction]] = {}
        self.action_registry = action_registry
        self.model_type = model_type
        self.default_invalidation = default_invalidation
        self.load_options = load_options or []

    def __call__[T: BaseAction](self, action_class: type[T]) -> type[T]:
        action_class.model = self.model_type
        action_key = action_class.action_key
        combined_key = self._get_action_key(action_key)

        self.actions[combined_key] = action_class

        if issubclass(action_class, BaseObjectAction):
            self.object_actions[combined_key] = action_class  # type: ignore[assignment]
        elif issubclass(action_class, BaseTopLevelAction):
            self.top_level_actions[combined_key] = action_class  # type: ignore[assignment]

        self.action_registry.register_action(combined_key, action_class)
        return action_class

    def _get_action_key(self, action_key: str) -> str:
        return f"{self.group_type.value}__{action_key.replace('.', '_')}"

    def get_action(self, action_key: str) -> type[BaseAction]:
        if action_key not in self.actions:
            raise NotFoundException(detail=f"Action {action_key} not found")
        return self.actions[action_key]

    async def get_object(self, object_id: UUID, transaction: AsyncSession) -> BaseDBModel | None:
        """Get object by id using the action group's model type.

        Returns `None` when the row is not visible (id absent or hidden by RLS).
        `trigger()` surfaces that as a 404 — we don't distinguish "doesn't exist"
        from "exists but invisible" to avoid id enumeration.
        """
        if self.model_type is None:
            raise Exception("This action group has no associated model type")

        result = await transaction.execute(
            select(self.model_type).where(self.model_type.id == object_id).options(*self.load_options)
        )
        return result.scalar_one_or_none()

    async def trigger(
        self,
        data: Any,  # Discriminated union instance
        deps: ActionDeps,
        object_id: UUID | None = None,
    ) -> ActionExecutionResponse:
        """Execute an action with proper dependency injection."""
        action_class: type[BaseAction] = self.action_registry._struct_to_action[type(data)]
        transaction = deps.transaction

        action_data = getattr(data, "data", data)

        if issubclass(action_class, BaseObjectAction):
            obj = await self.get_object(object_id=object_id, transaction=transaction) if object_id else None
            if obj is None:
                raise NotFoundException(detail=f"Object action {action_class.__name__} requires object_id")
            # `is_available` is the single source of truth for both UI visibility
            # and execution authorization. Checking here prevents a client from
            # bypassing a hidden action via a direct API call.
            if not action_class.is_available(obj, deps):
                logger.warning(
                    "Action %s blocked for user %s on object %s",
                    action_class.__name__,
                    getattr(deps.user, "id", None),
                    object_id,
                )
                raise PermissionDeniedException(
                    detail=f"Action {action_class.__name__} is not available in the current state"
                )
            disabled_reason = action_class.is_disabled(obj, deps)
            if disabled_reason is not None:
                raise PermissionDeniedException(detail=disabled_reason.message)
            actions_execution_response = await action_class.execute(obj, action_data, transaction, deps)
        elif issubclass(action_class, BaseTopLevelAction):
            if not action_class.is_available(deps):
                logger.warning(
                    "Top-level action %s blocked for user %s",
                    action_class.__name__,
                    getattr(deps.user, "id", None),
                )
                raise PermissionDeniedException(detail=f"Action {action_class.__name__} is not available for this user")
            disabled_reason = action_class.is_disabled(deps)
            if disabled_reason is not None:
                raise PermissionDeniedException(detail=disabled_reason.message)
            actions_execution_response = await action_class.execute(action_data, transaction, deps)
        else:
            raise TypeError(f"Action {action_class.__name__} must inherit from BaseObjectAction or BaseTopLevelAction")

        if not actions_execution_response.invalidate_queries and self.default_invalidation:
            actions_execution_response.invalidate_queries.append(self.default_invalidation)

        return actions_execution_response

    def get_available_actions(
        self,
        deps: ActionDeps,
        obj: BaseDBModel | None = None,
    ) -> list[ActionDTO]:
        available: list[tuple[str, type[BaseAction], DisabledReason | None]] = []
        if obj is not None:
            for action_key, action_class in self.object_actions.items():
                if action_class.is_hidden:
                    continue
                if action_class.is_available(obj, deps):
                    available.append((action_key, action_class, action_class.is_disabled(obj, deps)))
        else:
            for action_key, action_class in self.top_level_actions.items():
                if action_class.is_hidden:
                    continue
                if action_class.is_available(deps):
                    available.append((action_key, action_class, action_class.is_disabled(deps)))

        available.sort(key=lambda x: x[1].priority)

        results: list[ActionDTO] = []
        for action_key, action_class, disabled_reason in available:
            label = action_class.get_label(obj, deps) if obj is not None else action_class.label
            results.append(
                ActionDTO(
                    action_group_type=self.group_type,
                    action=action_key,
                    label=label,
                    is_bulk_allowed=action_class.is_bulk_allowed,
                    priority=action_class.priority,
                    icon=action_class.icon.value if action_class.icon else None,
                    confirmation_message=action_class.confirmation_message,
                    should_redirect_to_parent=action_class.should_redirect_to_parent,
                    disabled_reason=disabled_reason,
                    target_state=(action_class.target_state.value if action_class.target_state is not None else None),
                )
            )
        return results


def action_group_factory[T: BaseDBModel](
    group_type: ActionGroupType,
    default_invalidation: str | None = None,
    model_type: type[T] | None = None,
    load_options: list[ExecutableOption] | None = None,
) -> ActionGroup:
    """Create + register an `ActionGroup` for `group_type`.

    Returns the group, which is itself the decorator domains apply to their action
    classes (`@my_group` on each `BaseObjectAction`/`BaseTopLevelAction` subclass).
    """
    registry = ActionRegistry()
    action_group = ActionGroup(
        group_type=group_type,
        action_registry=registry,
        model_type=model_type,
        default_invalidation=default_invalidation,
        load_options=load_options,
    )
    registry.register(group_type, action_group)

    return action_group
