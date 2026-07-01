from __future__ import annotations

import logging
from typing import Any

from msgspec import structs
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.base.models import BaseDBModel
from app.platform.base.schemas import BaseSchema

logger = logging.getLogger(__name__)


async def create_model[T: BaseDBModel](
    session: AsyncSession,
    model_class: type[T],
    create_vals: BaseSchema,
    ignore_fields: list[str] | None = None,
) -> T:
    """Create a model instance from a struct DTO (skipping None / ignored fields)."""
    ignore_fields = ignore_fields or []
    data = {f: v for f, v in structs.asdict(create_vals).items() if v is not None and f not in ignore_fields}

    obj = model_class(**data)
    session.add(obj)
    await session.flush()
    return obj


async def update_model[T: BaseDBModel](
    session: AsyncSession,
    model_instance: T,
    update_vals: BaseSchema,
) -> T:
    """Apply struct updates to a model instance and flush.

    Supports nested structs: a `foo` struct value updates the existing related
    object's fields when the model exposes a `foo_id` FK column.
    """
    update_dict = structs.asdict(update_vals)
    fields_to_update: dict[str, Any] = {}
    for k, v in update_dict.items():
        if hasattr(v, "__struct_fields__"):
            fields_to_update[k] = structs.asdict(v)
        else:
            fields_to_update[k] = v

    for field, value in fields_to_update.items():
        if not hasattr(model_instance, field):
            continue
        nested_id_field = f"{field}_id"
        if hasattr(model_instance, nested_id_field):
            if value is None:
                setattr(model_instance, nested_id_field, None)
            elif isinstance(value, dict):
                existing = getattr(model_instance, field, None)
                if existing:
                    for nf, nv in value.items():
                        if hasattr(existing, nf):
                            setattr(existing, nf, nv)
                else:
                    logger.warning("Cannot auto-create nested object for field '%s'", field)
            else:
                logger.warning("Unexpected value type for nested field '%s': %s", field, type(value))
        else:
            setattr(model_instance, field, value)

    await session.flush()
    return model_instance
