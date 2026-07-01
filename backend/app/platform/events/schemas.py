"""Typed schemas for event_data payloads."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


def _serialize_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    return value


def make_field_changes(old_values: dict[str, Any], new_values: dict[str, Any]) -> dict[str, FieldChange]:
    """Build a {field: FieldChange} dict containing only fields whose value changed."""
    changes: dict[str, FieldChange] = {}
    for field, old in old_values.items():
        if field in new_values and old != new_values[field]:
            changes[field] = FieldChange(
                old=_serialize_value(old),
                new=_serialize_value(new_values[field]),
            )
    return changes


@dataclass
class FieldChange:
    old: Any
    new: Any


@dataclass
class UpdatedEventData:
    changes: dict[str, FieldChange]


@dataclass
class StateChangedEventData:
    state: FieldChange
    reason: str | None = None
    metadata: dict[str, Any] | None = None


@dataclass
class CreatedEventData:
    initial_values: dict[str, Any]


@dataclass
class CustomEventData:
    action: str
    payload: dict[str, Any] | None = None
