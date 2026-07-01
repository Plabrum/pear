from __future__ import annotations

from alembic_utils.pg_function import PGFunction

from app.domain.contacts.enums import WingpersonStatus

# The DB literal the `wingperson_status` TEXT column actually holds for "active".
# (TextEnum stores `.name`, so this is "ACTIVE".)
_ACTIVE_WINGPERSON_STATUS: str = WingpersonStatus.ACTIVE.name


# ── public.current_user_id() ─────────────────────────────────────────────────
# Reads the `app.user_id` GUC set by the per-request transaction. `missing_ok =
# true` => NULL when unset, so policies fail closed for unauthenticated sessions.
CURRENT_USER_ID_SQL = """
CREATE OR REPLACE FUNCTION public.current_user_id()
RETURNS uuid
LANGUAGE sql
STABLE
AS $$
  SELECT NULLIF(current_setting('app.user_id', true), '')::uuid
$$;
""".strip()


# ── public.is_system_mode() ──────────────────────────────────────────────────
# The trusted-operation RLS bypass. `app.is_system_mode` is set true ONLY by
# `AuthService` (first-login bootstrap, before any `app.user_id` exists) and by
# system/worker jobs; the normal request path defensively forces it false (see
# `provide_transaction`). Every Pear policy ORs `public.is_system_mode()` ahead of
# its relationship condition so those trusted operations can write. `missing_ok =
# true` + the `nullif(...,'')` guard => false when unset/empty, so the escape is
# closed by default and policies fail closed for ordinary unauthenticated sessions.
IS_SYSTEM_MODE_SQL = """
CREATE OR REPLACE FUNCTION public.is_system_mode()
RETURNS boolean
LANGUAGE sql
STABLE
AS $$
  SELECT coalesce(nullif(current_setting('app.is_system_mode', true), '')::boolean, false)
$$;
""".strip()


# ── public.is_active_wingperson(_dater uuid) ─────────────────────────────────
# True when the current user is an active wingperson for `_dater`. The status
# compares against the `TextEnum` name (`'ACTIVE'`), interpolated from the enum.
IS_ACTIVE_WINGPERSON_SQL = f"""
CREATE OR REPLACE FUNCTION public.is_active_wingperson(_dater uuid)
RETURNS boolean
LANGUAGE sql
STABLE
SECURITY INVOKER
SET search_path = public
AS $$
  SELECT EXISTS (
    SELECT 1 FROM public.contacts
    WHERE user_id = _dater
      AND winger_id = public.current_user_id()
      AND wingperson_status = '{_ACTIVE_WINGPERSON_STATUS}'
  );
$$;
""".strip()


# ── alembic_utils entities (autogenerate-friendly) ───────────────────────────
# `signature` is the function's call signature; `definition` is everything from
# `returns` onward (PGFunction.from_sql parses on the `returns` keyword).
CURRENT_USER_ID_FN = PGFunction(
    schema="public",
    signature="current_user_id()",
    definition="""
        returns uuid
        language sql
        stable
        as $$
          select nullif(current_setting('app.user_id', true), '')::uuid
        $$
    """,
)

IS_SYSTEM_MODE_FN = PGFunction(
    schema="public",
    signature="is_system_mode()",
    definition="""
        returns boolean
        language sql
        stable
        as $$
          select coalesce(nullif(current_setting('app.is_system_mode', true), '')::boolean, false)
        $$
    """,
)

IS_ACTIVE_WINGPERSON_FN = PGFunction(
    schema="public",
    signature="is_active_wingperson(_dater uuid)",
    definition=f"""
        returns boolean
        language sql
        stable
        security invoker
        set search_path = public
        as $$
          select exists (
            select 1 from public.contacts
            where user_id = _dater
              and winger_id = public.current_user_id()
              and wingperson_status = '{_ACTIVE_WINGPERSON_STATUS}'
          );
        $$
    """,
)


# Consumed by alembic/env.py (parallel to RLS_POLICY_REGISTRY).
# `current_user_id` MUST be created before any policy that calls it, and before
# `is_active_wingperson` (which depends on it) — list it first. `is_system_mode`
# is standalone but every policy ORs it, so it too must exist before the policies.
RLS_FUNCTION_REGISTRY: list[PGFunction] = [
    CURRENT_USER_ID_FN,
    IS_SYSTEM_MODE_FN,
    IS_ACTIVE_WINGPERSON_FN,
]


__all__ = [
    "CURRENT_USER_ID_FN",
    "CURRENT_USER_ID_SQL",
    "IS_ACTIVE_WINGPERSON_FN",
    "IS_ACTIVE_WINGPERSON_SQL",
    "IS_SYSTEM_MODE_FN",
    "IS_SYSTEM_MODE_SQL",
    "RLS_FUNCTION_REGISTRY",
]
