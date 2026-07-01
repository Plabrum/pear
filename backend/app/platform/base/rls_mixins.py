from typing import Any

from alembic_utils.pg_policy import PGPolicy

from app.platform.base.models import BaseDBModel

# Global registry for RLS policies — consumed by alembic env.py
RLS_POLICY_REGISTRY: list[PGPolicy] = []


def _register_policy(tablename: str, signature: str, definition: str) -> None:
    """Enroll a table for RLS and append one PGPolicy to the shared registry.

    Idempotent on (on_entity, signature): a model imported more than once will not
    double-register its policy.
    """
    BaseDBModel.metadata.info.setdefault("rls", set()).add(tablename)

    on_entity = f"public.{tablename}"
    existing = {(p.on_entity, p.signature) for p in RLS_POLICY_REGISTRY}
    if (on_entity, signature) in existing:
        return

    RLS_POLICY_REGISTRY.append(
        PGPolicy(
            schema="public",
            signature=signature,
            on_entity=on_entity,
            definition=definition.strip(),
        )
    )


def _user_scoped_definition(user_id_column: str) -> str:
    """`FOR ALL` policy: owner-or-system access on every CRUD command.

    The USING clause governs SELECT/UPDATE/DELETE (and the existing-row check of
    UPDATE); the identical WITH CHECK clause governs INSERT (and the new-row of
    UPDATE). The `public.is_system_mode()` escape is ORed first so trusted
    system/worker operations bypass the ownership predicate, consistent with the
    rest of the policy set.
    """
    predicate = f"public.is_system_mode() OR {user_id_column} = public.current_user_id()"
    return f"""
        AS PERMISSIVE
        FOR ALL
        TO pear_app
        USING ({predicate})
        WITH CHECK ({predicate})
    """


def _wingperson_scoped_definition(owner_column: str) -> str:
    """`FOR ALL` policy: owner, an active wingperson of the owner, or system.

    Extends the user-scoped predicate with `public.is_active_wingperson(<owner>)`,
    so a winger who is ACTIVE for the owning dater can also reach the row. USING
    governs SELECT/UPDATE/DELETE and the identical WITH CHECK governs INSERT.
    """
    predicate = (
        f"public.is_system_mode() "
        f"OR {owner_column} = public.current_user_id() "
        f"OR public.is_active_wingperson({owner_column})"
    )
    return f"""
        AS PERMISSIVE
        FOR ALL
        TO pear_app
        USING ({predicate})
        WITH CHECK ({predicate})
    """


class UserScopedMixin:
    """Marker mixin for tables whose rows belong to a single user.

    Does NOT add columns — the model must define its own owner FK (default
    `user_id`, overridable via `user_id_column=`). Registers a generic
    owner-scoped RLS policy so a row is accessible only to its owner (or in system
    mode). Relationship-aware policies that diverge from this shape live in
    `rls_policies.py`; this mixin stays minimal/generic and is the default for new
    user-scoped tables.
    """

    def __init_subclass__(cls, user_id_column: str = "user_id", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "__tablename__"):
            return

        tablename: str = cls.__tablename__  # type: ignore[misc]
        _register_policy(tablename, "user_scope_policy", _user_scoped_definition(user_id_column))


class WingpersonScopedMixin:
    """Marker mixin for tables a dater AND their active wingperson may access.

    Does NOT add columns. The owner column (default `user_id`, overridable via
    `owner_column=`) must reference `profiles(id)` — `public.is_active_wingperson`
    looks up an ACTIVE contact whose `user_id` equals that owner. Registers an RLS
    policy granting access to the owner OR an active wingperson of that owner (or in
    system mode). The default for new wingperson-scoped tables.
    """

    def __init_subclass__(cls, owner_column: str = "user_id", **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        if not hasattr(cls, "__tablename__"):
            return

        tablename: str = cls.__tablename__  # type: ignore[misc]
        _register_policy(tablename, "wingperson_scope_policy", _wingperson_scoped_definition(owner_column))
