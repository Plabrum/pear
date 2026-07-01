"""Filter and sort definitions for CRUD list endpoints.

Filter structs use msgspec tagged unions so the client sends:
    {"type": "text", "column": "name", "operation": "contains", "value": "smith"}

apply_filter() and apply_sorts() silently skip unknown or disallowed columns
to avoid leaking schema information.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum, auto
from typing import Literal

from msgspec import Struct
from sqlalchemy import Select

from app.platform.base.models import BaseDBModel


class FilterType(StrEnum):
    TEXT = auto()
    RANGE = auto()
    DATE = auto()
    BOOLEAN = auto()
    ENUM = auto()
    NULL = auto()


class TextFilter(Struct, tag=FilterType.TEXT.value):
    column: str
    operation: Literal["contains", "starts_with", "ends_with", "equals"]
    value: str


class RangeFilter(Struct, tag=FilterType.RANGE.value):
    column: str
    start: int | float | None = None
    finish: int | float | None = None


class DateFilter(Struct, tag=FilterType.DATE.value):
    column: str
    start: datetime | None = None
    finish: datetime | None = None


class BooleanFilter(Struct, tag=FilterType.BOOLEAN.value):
    column: str
    value: bool


class EnumFilter(Struct, tag=FilterType.ENUM.value):
    column: str
    values: list[str]


class NullFilter(Struct, tag=FilterType.NULL.value):
    """Match rows where `column IS NULL` (is_null=True) or `IS NOT NULL` (is_null=False)."""

    column: str
    is_null: bool


FilterDefinition = TextFilter | RangeFilter | DateFilter | BooleanFilter | EnumFilter | NullFilter


class SortDirection(StrEnum):
    ASC = auto()
    DESC = auto()


class SortDefinition(Struct):
    column: str
    direction: SortDirection


def _resolve_column(
    model: type[BaseDBModel],
    column_name: str,
    allowed_columns: set[str] | None,
):
    """Resolve a column name to a SQLAlchemy column attribute, or None."""
    if allowed_columns is not None and column_name not in allowed_columns:
        return None
    return getattr(model, column_name, None)


def apply_filter(
    query: Select,
    model: type[BaseDBModel],
    f: FilterDefinition,
    allowed_columns: set[str] | None = None,
) -> Select:
    col = _resolve_column(model, f.column, allowed_columns)
    if col is None:
        return query

    match f:
        case TextFilter(operation="equals", value=v):
            return query.where(col == v)
        case TextFilter(operation="contains", value=v):
            return query.where(col.ilike(f"%{v}%"))
        case TextFilter(operation="starts_with", value=v):
            return query.where(col.ilike(f"{v}%"))
        case TextFilter(operation="ends_with", value=v):
            return query.where(col.ilike(f"%{v}"))
        case RangeFilter(start=s, finish=fin):
            if s is not None:
                query = query.where(col >= s)
            if fin is not None:
                query = query.where(col <= fin)
            return query
        case DateFilter(start=s, finish=fin):
            if s is not None:
                query = query.where(col >= s)
            if fin is not None:
                query = query.where(col <= fin)
            return query
        case BooleanFilter(value=v):
            return query.where(col.is_(v))
        case EnumFilter(values=vals):
            return query.where(col.in_(vals))
        case NullFilter(is_null=True):
            return query.where(col.is_(None))
        case NullFilter(is_null=False):
            return query.where(col.is_not(None))
        case _:
            return query


def apply_sorts(
    query: Select,
    model: type[BaseDBModel],
    sorts: list[SortDefinition],
    allowed_columns: set[str] | None = None,
) -> Select:
    for sort in sorts:
        col = _resolve_column(model, sort.column, allowed_columns)
        if col is None:
            continue
        if sort.direction == SortDirection.ASC:
            query = query.order_by(col.asc())
        else:
            query = query.order_by(col.desc())
    return query
