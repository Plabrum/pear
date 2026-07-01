from __future__ import annotations

from app.platform.actions.base import ActionGroup
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.registry import ActionRegistry
from app.platform.actions.schemas import ActionDTO
from app.platform.base.models import BaseDBModel


def resolve_group(group_type: ActionGroupType) -> ActionGroup:
    """Resolve an action group by its EXPLICIT type.

    Always prefer this over ``ActionRegistry().find_by_model(...)``: a model can be
    bound to more than one group (``DatingProfile`` has both the edit group and the
    swipe group), and ``find_by_model`` would return whichever registered first.
    Groups are registered at boot by ``discover_and_import`` in
    ``app/platform/actions/routes.py``, so the lookup always succeeds in a request.
    """
    return ActionRegistry().get_class(group_type)


def actions_for(
    group: ActionGroup,
    deps: ActionDeps,
    obj: BaseDBModel | None,
) -> list[ActionDTO]:
    """The actions available on one object — ready to set on an ``Actionable`` read
    struct's ``actions`` field. ``obj=None`` returns the group's top-level actions.

    Pure and synchronous: ``get_available_actions`` does no I/O, so per-row
    hydration adds zero DB round-trips. The caller MUST pass an object that already
    carries every scalar column the group's ``is_available`` / ``is_disabled`` read
    — true for any loaded ORM row, and for the deliberately scalar-only transient
    stubs some bespoke read routes build (e.g. a ``Match``/``DatingProfile`` with
    just its identity columns set). A gating predicate must never touch a
    relationship, or it would lazy-load inside this sync call and raise.
    """
    return group.get_available_actions(deps, obj=obj)
