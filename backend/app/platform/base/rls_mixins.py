from typing import Any

from alembic_utils.pg_policy import PGPolicy

from app.platform.base.models import BaseDBModel

# Global registry for RLS policies — consumed by alembic env.py
RLS_POLICY_REGISTRY: list[PGPolicy] = []


# Generic user-ownership policy: a row is visible to the user whose id is in the
# row's `user_id` column, or when running in system mode (the SYSTEM actor used
# for system-driven transitions, migrations, and jobs).
USER_SCOPED_POLICY = """
    AS PERMISSIVE
    FOR ALL
    USING (
        NULLIF(current_setting('app.is_system_mode', true), '')::boolean IS TRUE
        OR (NULLIF(current_setting('app.user_id', true), '') IS NOT NULL
            AND user_id = NULLIF(current_setting('app.user_id', true), '')::uuid)
    )
"""


class UserScopedMixin:
    """Marker mixin for tables whose rows belong to a single user.

    Does NOT add columns — the model must define its own `user_id` FK.
    Registers a generic user-scoped RLS policy: only the owning user (or system
    mode) can access rows. Relationship-aware policies live in `rls_policies.py`;
    this mixin stays minimal/generic.
    """

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "__tablename__"):
            return

        tablename: str = cls.__tablename__  # type: ignore[misc]

        # Register table for RLS enablement (read by the comparator).
        BaseDBModel.metadata.info.setdefault("rls", set()).add(tablename)

        RLS_POLICY_REGISTRY.append(
            PGPolicy(
                schema="public",
                signature="user_scope_policy",
                on_entity=f"public.{tablename}",
                definition=USER_SCOPED_POLICY,
            )
        )
