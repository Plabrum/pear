"""Core state machine types: Transition, State, StateMachine, StateMachineService.

Adapted from sloopquest: roles are Pear's dater/winger/SYSTEM; SYSTEM transitions
write a NULL actor_id (no integer sentinel id); ids are UUIDs; the emitted
STATE_CHANGED event has no organization scoping and uses the trimmed sync
`emit_event`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.base.models import BaseDBModel
from app.platform.events.enums import EventType
from app.platform.events.schemas import FieldChange, StateChangedEventData
from app.platform.events.service import emit_event
from app.platform.state_machine.exceptions import InvalidTransitionError
from app.platform.state_machine.models import StateTransitionLog
from app.platform.state_machine.roles import Actor, Role

logger = logging.getLogger(__name__)


def _humanize(value: Any) -> str:
    """Turn an enum value like 'on_break' into 'On Break'."""
    s = value.value if isinstance(value, Enum) else str(value)
    return s.replace("_", " ").title()


@dataclass(frozen=True)
class Transition[E: Enum]:
    """One outbound edge from a state.

    roles semantics:
        {Role.X, ...}      -> specific roles; use {Role.SYSTEM} for system-only edges
        empty set          -> any authenticated role (not recommended — be explicit)
    """

    to: E
    roles: frozenset[Role]

    def __init__(self, to: E, *, roles: set[Role] | frozenset[Role]) -> None:
        object.__setattr__(self, "to", to)
        object.__setattr__(self, "roles", frozenset(roles))


class State[E: Enum, M: BaseDBModel]:
    """Base class for a state definition. Subclass per state in a machine."""

    value: ClassVar[Enum]
    transitions: ClassVar[list[Transition]]

    async def on_enter(
        self,
        service: StateMachineService,
        obj: M,
        from_state: E,
        context: dict[str, Any] | None,
    ) -> None:
        """Called after obj.state is set and the log row is written. Side effects only."""

    async def on_exit(
        self,
        service: StateMachineService,
        obj: M,
        to_state: E,
        context: dict[str, Any] | None,
    ) -> None:
        """Called before obj.state is changed. Side effects only."""

    def allowed_for(self, user_role: Role) -> list[E]:
        """Return target states reachable from this state for the given caller role."""
        return [t.to for t in self.transitions if not t.roles or user_role in t.roles]

    def get_transition(self, to: E, caller_role: Role) -> Transition[E] | None:
        """Return the first transition to the target state accessible by caller_role."""
        return next(
            (t for t in self.transitions if t.to == to and (not t.roles or caller_role in t.roles)),
            None,
        )


STATE_MACHINE_REGISTRY: dict[type[Enum], StateMachine[Any, Any]] = {}


@dataclass
class StateMachine[E: Enum, M: BaseDBModel]:
    """Pure definition — no session, no DI. Defined at module level per domain."""

    enum_type: type[E]
    states: dict[E, type[State[E, M]]]

    def __post_init__(self) -> None:
        STATE_MACHINE_REGISTRY[self.enum_type] = self

    def get_state(self, obj: M) -> State[E, M]:
        current = self.enum_type(obj.state)  # type: ignore[attr-defined]
        return self.states[current]()

    def can_transition(self, obj: M, to: E, user_role: Role) -> bool:
        """Check if a user with this role can transition obj to the target state."""
        state = self.get_state(obj)
        return to in state.allowed_for(user_role)

    def has_any_transition(self, obj: M, user_role: Role) -> bool:
        """Check if a user with this role can make any transition from the current state."""
        state = self.get_state(obj)
        return len(state.allowed_for(user_role)) > 0


class StateMachineService:
    """Session-bound service. One instance per request (provided via Litestar DI)."""

    def __init__(self, transaction: AsyncSession) -> None:
        self.transaction = transaction

    async def transition(
        self,
        machine: StateMachine[Any, Any],
        obj: Any,
        to: Any,
        *,
        actor: Actor,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Human-initiated transition. Validates topology and the actor's role."""
        state = machine.get_state(obj)
        transition = state.get_transition(to, actor.role)

        from_label = _humanize(obj.state)
        to_label = _humanize(to)

        if transition is None:
            raise InvalidTransitionError(
                detail=f"This item cannot be moved from {from_label} to {to_label}.",
            )

        await self._execute_transition(machine, obj, state, to, actor_id=actor.id, context=context)

    async def system_transition(
        self,
        machine: StateMachine[Any, Any],
        obj: Any,
        to: Any,
        *,
        context: dict[str, Any] | None = None,
    ) -> None:
        """System transition — only edges that include Role.SYSTEM are permitted.

        Writes a NULL actor_id on the audit log (no human actor).
        """
        state = machine.get_state(obj)
        transition = state.get_transition(to, Role.SYSTEM)

        if transition is None:
            raise InvalidTransitionError(
                detail=f"No system transition from {obj.state!r} to {to!r}",
            )

        await self._execute_transition(machine, obj, state, to, actor_id=None, context=context)

    def allowed_transitions(
        self,
        machine: StateMachine[Any, Any],
        obj: Any,
        actor: Actor,
    ) -> frozenset[Any]:
        """States this user can transition obj to from its current state."""
        state = machine.get_state(obj)
        return frozenset(state.allowed_for(actor.role))

    async def _execute_transition(
        self,
        machine: StateMachine[Any, Any],
        obj: Any,
        current_state: State[Any, Any],
        to: Any,
        *,
        actor_id: UUID | None,
        context: dict[str, Any] | None,
    ) -> None:
        """Shared execution: on_exit -> set state -> log -> on_enter -> emit event."""
        from_state = obj.state

        # 1. on_exit
        await current_state.on_exit(self, obj, to, context)

        # 2. Set state
        obj.state = to

        # 3. Write audit log (stores .value for human readability)
        from_value = from_state.value if hasattr(from_state, "value") else str(from_state)
        to_value = to.value if hasattr(to, "value") else str(to)
        log = StateTransitionLog(
            object_type=obj.__tablename__,
            object_id=obj.id,
            from_state=from_value,
            to_state=to_value,
            actor_id=actor_id,
            context=context,
        )
        self.transaction.add(log)

        # 4. on_enter
        target_state = machine.states[to]()
        await target_state.on_enter(self, obj, from_state, context)

        # 5. Emit STATE_CHANGED event (best-effort — don't break the transition).
        await self._emit_state_changed(obj, actor_id, from_value, to_value, context)

    async def _emit_state_changed(
        self,
        obj: Any,
        actor_id: UUID | None,
        from_value: str,
        to_value: str,
        context: dict[str, Any] | None,
    ) -> None:
        try:
            await emit_event(
                session=self.transaction,
                event_type=EventType.STATE_CHANGED,
                obj=obj,
                user_id=actor_id,
                event_data=StateChangedEventData(
                    state=FieldChange(old=from_value, new=to_value),
                    metadata=context,
                ),
            )
        except Exception:
            logger.exception("Failed to emit STATE_CHANGED event for %s#%s", obj.__tablename__, obj.id)
