from typing import TYPE_CHECKING, Self

from app.platform.actions.enums import ActionGroupType
from app.platform.base.registry import BaseRegistry

if TYPE_CHECKING:
    from app.platform.actions.base import ActionGroup, BaseAction


class ActionRegistry(
    BaseRegistry[ActionGroupType, "ActionGroup"],
):
    """Singleton registry of action groups, keyed by `ActionGroupType`.

    Also keeps a flat map of every registered action (by combined key) and a
    reverse map from each generated request struct back to its action class —
    used by the router to dispatch a decoded request body to the right action.
    """

    _flat_registry: dict[str, type["BaseAction"]]
    _struct_to_action: dict[type, type["BaseAction"]]

    def __new__(cls: type[Self]) -> Self:
        inst = super().__new__(cls)
        if not hasattr(inst, "_flat_registry"):
            inst._flat_registry = {}
        if not hasattr(inst, "_struct_to_action"):
            inst._struct_to_action = {}
        return inst

    def register(
        self,
        key: ActionGroupType,
        value: "ActionGroup",
    ) -> None:
        self._registry[key] = value

    def register_action(self, action_key: str, action_class: type["BaseAction"]) -> None:
        self._flat_registry[action_key] = action_class

    def find_by_model(self, model: type) -> "ActionGroup | None":
        for group in self._registry.values():
            if group.model_type is model:
                return group
        return None
