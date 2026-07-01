import inspect
import sys
from functools import reduce
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    TypeAliasType,
    get_args,
    get_origin,
    get_type_hints,
)
from uuid import UUID

import msgspec

from app.platform.actions.enums import ActionGroupType, ActionResultType
from app.platform.base.schemas import BaseSchema

if TYPE_CHECKING:
    from app.platform.actions.registry import ActionRegistry


class ActionCTA(BaseSchema):
    label: str
    path: str


class DisabledReason(BaseSchema):
    """Why an available action cannot currently be executed.

    An action that is *available* (visible) may still be *disabled* — e.g. a winger
    can see "Suggest" but it is disabled until the dater is in `winging` status.
    """

    message: str
    cta: ActionCTA | None = None


class ActionDTO(BaseSchema):
    """Client-facing description of one action surfaced for an object or group."""

    action: str
    label: str
    action_group_type: ActionGroupType
    is_bulk_allowed: bool = False
    available: bool = True
    priority: int = 100
    icon: str | None = None
    confirmation_message: str | None = None
    should_redirect_to_parent: bool = False
    disabled_reason: DisabledReason | None = None
    # When set, the action transitions its object to this state value.
    # Frontends derive `is_state_transition` as `target_state is not None`.
    target_state: str | None = None


class ActionExecutionRequest(BaseSchema):
    action_group: ActionGroupType
    object_id: UUID


class RedirectActionResult(BaseSchema, tag=ActionResultType.REDIRECT.value):
    path: str  # e.g. "/matches/<uuid>" or ".." for parent


class DownloadFileActionResult(BaseSchema, tag=ActionResultType.DOWNLOAD_FILE.value):
    url: str
    filename: str


class CopyToClipboardActionResult(BaseSchema, tag=ActionResultType.COPY_TO_CLIPBOARD.value):
    text: str
    toast: str | None = None


ActionResult = RedirectActionResult | DownloadFileActionResult | CopyToClipboardActionResult


class ActionExecutionResponse(BaseSchema):
    """Response from action execution with metadata for navigation and query invalidation."""

    message: str = ""
    invalidate_queries: list[str] = []  # Query keys the client should invalidate
    action_result: ActionResult | None = None  # Follow-up the client should perform
    created_id: UUID | None = None  # ID of a newly created object (for create actions)


class ActionListResponse(BaseSchema):
    actions: list[ActionDTO]


# CRUD list and detail schemas inherit from these so the `actions` field is part
# of every resource's read contract — the CRUD layer hydrates it at request time.
# `kw_only=True` lets subclasses declare required fields without ordering issues.
class Actionable(BaseSchema, kw_only=True):
    actions: list[ActionDTO] = []


class ActionableList(Actionable):
    pass


class ActionableDetail(Actionable):
    pass


# --- Helper functions for Action union generation -------------------------------


def _base_type(tp: Any) -> Any:
    """Extract base type from Annotated types."""
    return get_args(tp)[0] if get_origin(tp) is Annotated else tp


def default_tp(tp: Any | None) -> list[tuple[str, Any]]:
    """Return struct field definitions for the provided data type."""
    if tp is None or tp is inspect._empty:
        return []
    if isinstance(tp, TypeAliasType):
        tp = getattr(tp, "__value__", tp)
    return [("data", tp)]


def _extract_data_param_type(action_cls: type) -> Any | None:
    """Extract the type annotation of the 'data' parameter from an action's execute method."""
    meth = getattr(action_cls, "execute")
    fn = meth.__func__ if isinstance(meth, classmethod | staticmethod) else meth
    fn = inspect.unwrap(fn)

    sig = inspect.signature(fn)
    if "data" not in sig.parameters:
        return None

    mod = sys.modules.get(action_cls.__module__)
    hints = get_type_hints(
        fn,
        globalns=getattr(mod, "__dict__", {}),
        localns=vars(action_cls),
        include_extras=True,
    )
    ann = hints.get("data", sig.parameters["data"].annotation)
    if ann is inspect._empty:
        raise TypeError(f"{action_cls.__name__}.execute 'data' is unannotated")
    return _base_type(ann)


def build_action_union(action_registry: "ActionRegistry") -> TypeAliasType:
    """Build a discriminated union type from all registered actions.

    Iterates through all registered actions, extracts their data parameter types,
    and creates a discriminated union with tag-based discrimination using the action key.
    The generated structs map back to their action class via `_struct_to_action`.
    """
    action_structs: list[type[msgspec.Struct]] = []

    for action_key, action_cls in action_registry._flat_registry.items():
        tp = _extract_data_param_type(action_cls)
        fields = default_tp(tp)

        struct_class = msgspec.defstruct(
            f"{action_cls.__name__}Action",
            fields,
            tag_field="action",
            tag=action_key,
        )
        action_structs.append(struct_class)

        action_registry._struct_to_action[struct_class] = action_cls

    _action_union = (
        reduce(lambda a, b: a | b, action_structs) if action_structs else msgspec.Struct  # type: ignore[arg-type, return-value]
    )
    return TypeAliasType("Action", _action_union)  # type: ignore[valid-type]
