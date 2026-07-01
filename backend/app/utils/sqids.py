from __future__ import annotations

from typing import Any

import sqids as _sqids
from litestar.openapi.spec import OpenAPIType, Schema
from litestar.plugins import OpenAPISchemaPlugin
from sqlalchemy import Integer, TypeDecorator

__all__ = [
    "sqid_decode",
    "sqid_encode",
    "Sqid",
    "SqidSchemaPlugin",
    "SqidType",
    "sqid_type_predicate",
    "sqid_enc_hook",
    "sqid_dec_hook",
]

sqid_encoder: _sqids.Sqids = _sqids.Sqids(
    alphabet="abcdefghijklmnopqrstuvwxyz",
    min_length=8,
)

# All Sqid-backed IDs are stored in Postgres INTEGER columns (see `SqidType`
# below). A Sqid that decodes to an int outside that range can never match a
# real row — and attempting to bind it as a query parameter raises a DataError
# at the SQL layer, which Litestar surfaces as 500. Reject at decode time so
# the caller gets a clean 400 instead.
_MAX_POSTGRES_INT = 2_147_483_647


def sqid_decode(value: str) -> int:
    decoded = sqid_encoder.decode(value)
    if len(decoded) != 1:
        raise ValueError(f"Invalid SQID: {value}")
    if decoded[0] < 0 or decoded[0] > _MAX_POSTGRES_INT:
        raise ValueError(f"Invalid SQID: {value} decodes to out-of-range integer")
    return decoded[0]


def sqid_encode(value: int) -> str:
    return sqid_encoder.encode([value])


class Sqid(int):
    """int subclass that serialises to its SQID string representation."""

    def __str__(self) -> str:
        return sqid_encode(int(self))


class SqidType(TypeDecorator):
    """SQLAlchemy column type: stores INTEGER, returns Sqid in Python."""

    impl = Integer
    cache_ok = True

    def process_result_value(self, value: int | None, dialect: Any) -> Sqid | None:
        return Sqid(value) if value is not None else None

    def process_bind_param(self, value: Any, dialect: Any) -> int | None:
        if value is None:
            return None
        if isinstance(value, int):
            return int(value)
        if isinstance(value, str):
            return sqid_decode(value)
        return int(value)


def sqid_type_predicate(type_: type) -> bool:
    return type_ is Sqid or (isinstance(type_, type) and issubclass(type_, Sqid))


def sqid_enc_hook(value: int) -> str:
    return sqid_encode(int(value))


def sqid_dec_hook(type_: type, obj: Any) -> Sqid:
    if sqid_type_predicate(type_):
        if isinstance(obj, str):
            if not obj:
                raise ValueError("Invalid SQID: empty string (send null instead)")
            return Sqid(sqid_decode(obj))
        if isinstance(obj, int):
            return Sqid(obj)
        raise TypeError(f"Expected str or int for Sqid, got {type(obj).__name__}: {obj}")
    raise NotImplementedError(f"Encountered unknown type: {type_}")


class SqidSchemaPlugin(OpenAPISchemaPlugin):
    @staticmethod
    def is_plugin_supported_type(value: object) -> bool:
        return value is Sqid

    def to_openapi_schema(self, field_definition: object, schema_creator: object) -> Schema:
        return Schema(
            type=OpenAPIType.STRING,
            description="SQID-encoded identifier",
            example="kmxpqdrv",
        )
