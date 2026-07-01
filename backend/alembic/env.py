from logging.config import fileConfig

from alembic.autogenerate import comparators
from alembic_utils.pg_function import PGFunction as PGFunctionType
from alembic_utils.pg_policy import PGPolicy as PGPolicyType
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Connection
from sqlalchemy.types import TypeDecorator

# Import RLS operations so custom ops are registered with Alembic
import app.platform.base.rls_operations  # noqa: F401

# Import the concrete Pear RLS policy set for its registration side effect:
# `register_pear_rls()` runs on import, appending all 31 PGPolicy entities to the
# shared `RLS_POLICY_REGISTRY` and recording the 11 RLS tables in
# `BaseDBModel.metadata.info["rls"]` (consumed by `compare_rls` to emit enable_rls).
import app.platform.base.rls_policies  # noqa: F401
from alembic import context
from app.config import config as app_config
from app.platform.base.models import BaseDBModel
from app.platform.base.rls_comparator import compare_rls
from app.platform.base.rls_functions import RLS_FUNCTION_REGISTRY
from app.platform.base.rls_mixins import RLS_POLICY_REGISTRY
from app.utils.discovery import discover_and_import

discover_and_import(["models.py", "models/**/*.py"])

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseDBModel.metadata
# `ADMIN_DB_URL` is the bare `postgresql://` sync URL (per the config contract).
# This project ships psycopg v3 (`psycopg[binary]`), not psycopg2, so pin the
# sync driver explicitly for SQLAlchemy's engine resolution.
database_url = app_config.ADMIN_DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)


# ── RLS policy registration ──────────────────────────────────────────────────
def get_existing_policies():
    """Filter RLS_POLICY_REGISTRY to only include policies for existing tables."""
    try:
        engine = create_engine(database_url)
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        engine.dispose()
    except Exception:
        return RLS_POLICY_REGISTRY

    return [p for p in RLS_POLICY_REGISTRY if p.on_entity.split(".")[-1] in existing_tables]


# Register the RLS helper functions BEFORE the policies. alembic_utils
# materializes each registered entity in a sandbox to diff it, so the functions
# (`current_user_id`, `is_active_wingperson`) must exist before the policies that
# call them are created. `current_user_id` is listed first in the registry, and
# `is_active_wingperson` depends on it, so list-order is correct.
register_entities(RLS_FUNCTION_REGISTRY, entity_types=[PGFunctionType])
register_entities(get_existing_policies(), entity_types=[PGPolicyType])
comparators.dispatch_for("table")(compare_rls)


def include_object(object, name, type_, reflected, compare_to):
    """Exclude SAQ tables from autogenerate migrations."""
    if type_ == "table" and name.startswith("saq_"):
        return False
    return True


def render_item(type_: str, obj: object, autogen_context: object) -> str | bool:
    """Tell Alembic how to render custom TypeDecorators in migration files."""
    if type_ == "type":
        class_name = obj.__class__.__name__
        if isinstance(obj, TypeDecorator):
            if class_name == "TextEnum":
                autogen_context.imports.add("from app.utils.textenum import TextEnum")  # type: ignore[union-attr]
                enum_cls = obj.enum_class  # type: ignore[attr-defined]
                module = enum_cls.__module__
                name = enum_cls.__qualname__
                autogen_context.imports.add(f"from {module} import {name}")  # type: ignore[union-attr]
                return f"TextEnum({name})"
    return False


def run_migrations_offline() -> None:
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        render_item=render_item,  # type: ignore[arg-type]
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        render_item=render_item,  # type: ignore[arg-type]
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = create_engine(database_url)
    with connectable.connect() as connection:
        do_run_migrations(connection)
    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
