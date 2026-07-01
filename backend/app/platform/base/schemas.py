from msgspec import Struct

from app.platform.base.filters import FilterDefinition, SortDefinition
from app.utils.sqids import Sqid


class BaseSchema(Struct):
    """Base schema class for all msgspec structs."""

    pass


class EntityRef(BaseSchema):
    """Reference to another resource — id, display label, and detail href."""

    id: Sqid
    label: str
    href: str


class ListRequest(Struct):
    """Request body for CRUD list endpoints."""

    filters: list[FilterDefinition] = []
    sorts: list[SortDefinition] = []
    search: str | None = None
    limit: int = 50
    offset: int = 0


class PagedResponse[T](Struct):
    """Paginated list response envelope."""

    items: list[T]
    total: int
    offset: int
    limit: int
    has_more: bool
