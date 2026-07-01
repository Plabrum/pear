from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, get_type_hints

from litestar import Controller, get, post
from litestar.exceptions import NotFoundException
from msgspec import Struct
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.base.filters import apply_filter, apply_sorts
from app.platform.base.models import BaseDBModel
from app.platform.base.registry import BaseRegistry
from app.platform.base.schemas import ListRequest, PagedResponse
from app.utils.sqids import Sqid

# Populated by make_crud_controller — exposed (e.g. via a /schema endpoint) for codegen.
_crud_metadata: dict[str, dict] = {}


@dataclass
class CRUDEntry:
    path: str
    config: "CRUDConfig"


class CRUDRegistry(BaseRegistry[type, CRUDEntry]):
    pass


@dataclass
class CRUDConfig[ModelT: BaseDBModel, ListT: Struct, DetailT: Struct]:
    """Declarative configuration for a resource's read endpoints."""

    model: type[ModelT]

    to_list_item: Callable[[ModelT, Any], ListT]
    to_detail: Callable[[ModelT, Any], DetailT]

    # "user": scope rows by `user_id` == current user (default).
    # "none": no implicit scoping — rely on RLS and/or base_query_modifier.
    scope: Literal["user", "none"] = "user"

    list_load_options: list[Any] = field(default_factory=list)
    detail_load_options: list[Any] = field(default_factory=list)

    filterable_columns: set[str] | None = None
    sortable_columns: set[str] | None = None
    default_sort: str | None = None  # e.g. "activity_date" — defaults to "created_at" desc

    # Label field used by entity combobox codegen.
    label_field: str | None = None

    # Codegen metadata hints.
    column_types: dict[str, str] = field(default_factory=dict)
    column_labels: dict[str, str] = field(default_factory=dict)

    # Custom filter handlers for columns that aren't direct model attributes.
    # Signature: (query, FilterDefinition) -> query
    custom_filters: dict[str, Callable] = field(default_factory=dict)

    extra_guards: list[Any] = field(default_factory=list)
    # Guards applied only to list (POST /) — on top of `extra_guards`.
    list_extra_guards: list[Any] = field(default_factory=list)
    # Guards applied only to detail (GET /{id}) — on top of `extra_guards`.
    detail_extra_guards: list[Any] = field(default_factory=list)

    # When False, don't generate the GET /{id} handler — the caller is
    # providing a custom detail handler (e.g. role-aware filtering).
    expose_detail: bool = True

    # Optional hook to modify the base query per-request (e.g. role-based scoping).
    # Signature: (query, user) -> query
    base_query_modifier: Callable[[Any, Any], Any] | None = None


def make_crud_controller[ModelT: BaseDBModel, ListT: Struct, DetailT: Struct](
    path: str,
    config: CRUDConfig[ModelT, ListT, DetailT],
) -> type[Controller]:
    """Generate a Litestar Controller with list (POST /) and detail (GET /{id}) routes."""
    model = config.model
    guards = [*config.extra_guards]
    list_guards = [*guards, *config.list_extra_guards]
    detail_guards = [*guards, *config.detail_extra_guards]
    model_name = model.__name__

    # Resolve scope column at factory time so we get a clean error if it's missing.
    if config.scope == "user":
        scope_col = getattr(model, "user_id")
    else:
        scope_col = None
    default_sort_col = getattr(model, config.default_sort or "created_at")

    # Infer concrete return types from callable annotations for OpenAPI generation.
    # PEP 695 type params aren't resolved at runtime, so Litestar needs concrete types.
    hints = get_type_hints(config.to_list_item)
    list_item_type = hints.get("return", Struct)
    detail_hints = get_type_hints(config.to_detail)
    detail_type = detail_hints.get("return", Struct)

    @post("/", guards=list_guards, tags=[model_name.lower()], status_code=200, operation_id=f"list_{model_name}")
    async def list_handler(
        self,
        data: ListRequest,
        user: Any,
        transaction: AsyncSession,
    ) -> PagedResponse:
        # Clamp limit and offset.
        limit = max(1, min(data.limit, 200))
        offset = max(0, data.offset)

        base = select(model)
        if scope_col is not None:
            base = base.where(scope_col == user.id)

        # Role-based query scoping.
        if config.base_query_modifier is not None:
            base = config.base_query_modifier(base, user)

        # Load options.
        for opt in config.list_load_options:
            base = base.options(opt)

        # Filters.
        for f in data.filters:
            if f.column in config.custom_filters:
                base = config.custom_filters[f.column](base, f)
            else:
                base = apply_filter(base, model, f, config.filterable_columns)

        # Sorts (default: created_at desc).
        if data.sorts:
            base = apply_sorts(base, model, data.sorts, config.sortable_columns)
        else:
            base = base.order_by(default_sort_col.desc())

        # Count total.
        count_q = select(func.count()).select_from(base.subquery())
        total = (await transaction.execute(count_q)).scalar_one()

        # Paginate.
        paginated = base.offset(offset).limit(limit)
        result = await transaction.execute(paginated)
        rows = list(result.scalars().all())

        items = [config.to_list_item(row, user) for row in rows]

        return PagedResponse(
            items=items,
            total=total,
            offset=offset,
            limit=limit,
            has_more=offset + len(items) < total,
        )

    list_handler.fn.__annotations__["return"] = PagedResponse[list_item_type]

    @get("/{id:str}", guards=detail_guards, tags=[model_name.lower()])
    async def detail_handler(
        self,
        id: Sqid,
        user: Any,
        transaction: AsyncSession,
    ) -> Struct:
        query = select(model).where(model.id == id)
        if scope_col is not None:
            query = query.where(scope_col == user.id)
        if config.base_query_modifier is not None:
            query = config.base_query_modifier(query, user)
        for opt in config.detail_load_options:
            query = query.options(opt)

        result = await transaction.execute(query)
        obj = result.unique().scalar_one_or_none()
        if obj is None:
            raise NotFoundException()

        return config.to_detail(obj, user)

    detail_handler.fn.__annotations__["return"] = detail_type

    # Build controller class dynamically.
    class_attrs: dict[str, Any] = {
        "path": path,
        "list_handler": list_handler,
    }
    if config.expose_detail:
        class_attrs["detail_handler"] = detail_handler

    controller_cls = type(
        f"{model_name}CRUDController",
        (Controller,),
        class_attrs,
    )

    # Register metadata for codegen.
    column_types = dict(config.column_types)
    column_labels = dict(config.column_labels)

    metadata: dict[str, object] = {
        "filterable": sorted(config.filterable_columns or []),
        "sortable": sorted(config.sortable_columns or []),
    }
    if column_types:
        metadata["column_types"] = column_types
    if column_labels:
        metadata["column_labels"] = column_labels
    _crud_metadata[f"list_{model_name}"] = metadata

    CRUDRegistry().register(model, CRUDEntry(path=path, config=config))

    return controller_cls
