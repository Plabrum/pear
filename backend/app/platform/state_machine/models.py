from enum import Enum
from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.platform.base.models import BaseDBModel
from app.utils.sqids import Sqid, SqidType
from app.utils.textenum import TextEnum


def get_state_machine_meta(model: type[BaseDBModel]) -> dict[str, Any] | None:
    """Return {column, states} if `model` has a state-machine `state` column."""
    state_col = model.__table__.columns.get("state")
    if state_col is None or not isinstance(state_col.type, TextEnum):
        return None
    return {
        "column": "state",
        "states": [v.value for v in state_col.type.enum_class],  # pyright: ignore[reportGeneralTypeIssues]
    }


class _StateMachineMixinBase[E: Enum](BaseDBModel):
    __abstract__ = True
    state: Mapped[E]


def StateMachineMixin[E: Enum](  # noqa: N802
    *, state_enum: type[E], initial_state: E
) -> type[_StateMachineMixinBase[E]]:
    """Factory returning an abstract mixin that adds a TextEnum `state` column.

    Usage:
        class Decision(
            StateMachineMixin(state_enum=DecisionStatus, initial_state=DecisionStatus.PENDING),
            UserScopedMixin,
        ):
            __tablename__ = "decisions"
    """

    class _Mixin(_StateMachineMixinBase[E]):
        __abstract__ = True

        @declared_attr
        def state(cls) -> Mapped[E]:  # noqa: N805
            return mapped_column(
                TextEnum(state_enum),
                index=True,
                nullable=False,
                default=initial_state,
                server_default=initial_state.name,
            )

        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)
            if not cls.__dict__.get("__abstract__", False):
                cls.__annotations__["state"] = Mapped[state_enum]

    return _Mixin


class StateTransitionLog(BaseDBModel):
    """Append-only audit log. One row per completed transition.

    `actor_id` is nullable: SYSTEM-initiated transitions have no human actor.
    `object_id` references the transitioned row by its integer primary key.
    """

    __tablename__ = "state_transition_logs"

    object_type: Mapped[str] = mapped_column(String, nullable=False)
    object_id: Mapped[Sqid] = mapped_column(SqidType, nullable=False)
    from_state: Mapped[str] = mapped_column(String, nullable=False)
    to_state: Mapped[str] = mapped_column(String, nullable=False)
    actor_id: Mapped[Sqid | None] = mapped_column(SqidType, nullable=True)
    context: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_stl_object_lookup", "object_type", "object_id"),)
