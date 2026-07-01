from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.utils.sqids import Sqid, SqidType


class BaseDBModel(DeclarativeBase):
    """Declarative base — provides id, audit, and soft-delete columns plus a model registry."""

    _model_registry: set[type["BaseDBModel"]] = set()

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "__tablename__"):
            BaseDBModel._model_registry.add(cls)

    @classmethod
    def get_all_models(cls) -> set[type["BaseDBModel"]]:
        return cls._model_registry

    id: Mapped[Sqid] = mapped_column(SqidType, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True),
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True),
        default=None,
        index=True,
    )

    def soft_delete(self) -> None:
        self.deleted_at = datetime.now(tz=UTC)

    def restore(self) -> None:
        self.deleted_at = None

    @hybrid_property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @is_deleted.inplace.expression
    @classmethod
    def _is_deleted_expression(cls) -> sa.ColumnElement[bool]:
        return cls.deleted_at.is_not(None)

    def to_dict(self) -> dict[str, Any]:
        return {col.name: getattr(self, col.name) for col in self.__table__.columns}
