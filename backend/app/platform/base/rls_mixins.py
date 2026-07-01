"""Policies-as-code: register RLS policies declaratively via model mixins.

This module ports the sloopquest MACHINERY only. Pear has NO organization concept
(it is relationship-scoped: dater <-> winger <-> match), so the org mixins/policies
are dropped. A single minimal, generic `UserScopedMixin` is kept as an example of
how a model opts a table into RLS and registers a policy.

The concrete Pear policies (relationship-aware: a winger may read their dater's
rows, matched users may read each other's messages, etc.) are Phase 4 work — they
will be authored as additional `PGPolicy` entries appended to `RLS_POLICY_REGISTRY`,
consumed by the Alembic env via `register_entities(RLS_POLICY_REGISTRY, ...)`.

Active scope is communicated to Postgres via the session variable set by
`provide_transaction` (requests) and `rls_transaction` (long-lived handlers):
    app.user_id        — current user (UUID, set from the decoded JWT `sub`)
    app.is_system_mode — bypass for migrations and system jobs / system-role transitions
"""

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
    mode) can access rows. Real Pear relationship-aware policies land in Phase 4;
    this stays minimal/generic.
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
