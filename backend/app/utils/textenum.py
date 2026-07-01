from enum import Enum
from typing import Any

from sqlalchemy import types
from sqlalchemy.ext.compiler import compiles


class TextEnum[E: Enum](types.TypeDecorator[E]):
    impl = types.Text
    cache_ok = True

    def __init__(self, enum_class: type[E], *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.enum_class = enum_class

    def process_bind_param(self, value: E | str | None, dialect: Any) -> str | None:
        """Python -> DB: store as enum .name (e.g. DATER)."""
        if value is None:
            return None
        if isinstance(value, Enum):  # check Enum before str — StrEnum is both
            return value.name
        # Resolve raw strings: try by .value first, then by .name
        try:
            return self.enum_class(value).name
        except (ValueError, KeyError):
            pass
        try:
            return self.enum_class[value].name
        except KeyError:
            return value

    def process_result_value(self, value: str | None, dialect: Any) -> E | None:
        """DB -> Python: look up by name."""
        if value is None:
            return None
        return self.enum_class[value]


@compiles(TextEnum, "postgresql")
def compile_text_enum(element: TextEnum, compiler: Any, **kw: Any) -> str:  # noqa: ARG001
    return "TEXT"
