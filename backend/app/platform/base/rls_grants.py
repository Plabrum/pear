"""`pear_app` application-role GRANTs (Phase 4 — B1, sloopquest role model).

The app connects as a dedicated NON-superuser, NON-owner LOGIN role, `pear_app`,
for *all* runtime work (requests, tasks, websockets). Because `pear_app` neither
owns the tables nor is a superuser, it is natively subject to `FORCE ROW LEVEL
SECURITY` — RLS is a genuine authorization floor, not something bypassed by an
owner/superuser connection. There is no per-request `SET ROLE` anymore: the
connection role *is* the non-superuser role from the moment it is opened.

This replaces the old Supabase-style `authenticator` (NOLOGIN) + `SET LOCAL role =
authenticated` downgrade. The trusted-operation escape is now the honored
`public.is_system_mode()` GUC (see `rls_functions.py`), not a superuser connection.

These GRANTs are the privilege *ceiling*; the policies in `rls_policies.py` are the
floor. Without table privileges, RLS has nothing to filter — so:

  1. schema usage for `pear_app`.
  2. CRUD on all existing tables + USAGE/SELECT on all sequences.
  3. EXECUTE on all functions (so policies can call current_user_id() etc.).
  4. `ALTER DEFAULT PRIVILEGES` so objects created by future migrations inherit
     the same grants without revisiting this block.

Everything is wrapped in a `pg_roles` existence guard so the migration still runs
on a bare Postgres where the role hasn't been provisioned. Repeated GRANTs are
no-ops in Postgres, so this stays idempotent/rerunnable.

Role CREATION is separate (`app_role_bootstrap_sql`): roles are cluster-global, not
schema objects, so they are created by the migration owner (admin) in an idempotent
DO block before the grants. The login password comes from `DB_APP_PASSWORD` (the
alembic env exposes it), defaulting to `pear_app` for local dev.

`{owner_role}` is the role that owns objects created by migrations (the role the
Alembic runner connects as — `ADMIN_DB_URL`'s user). `DEFAULT_OWNER_ROLE` is
`postgres`; override via the `owner_role=` kwarg if different.
"""

from __future__ import annotations

# Role the migration runner connects as (owns newly-created objects). This is the
# `DB_USER` from `ADMIN_DB_URL`; Supabase used `postgres` — keep that default.
DEFAULT_OWNER_ROLE = "postgres"

# Dedicated NON-superuser LOGIN role the app connects as for ALL runtime work.
# RLS policies are granted `TO` this role; it owns nothing, so FORCE RLS applies.
APP_ROLE = "pear_app"

# Local-dev default password. Prod overrides via DB_APP_PASSWORD (Secrets Manager).
DEFAULT_APP_PASSWORD = "pear_app"


def _quote_literal(value: str) -> str:
    """Single-quote a string literal for safe inlining into SQL."""
    return "'" + value.replace("'", "''") + "'"


def app_role_bootstrap_sql(app_password: str = DEFAULT_APP_PASSWORD) -> str:
    """Idempotently CREATE the `pear_app` login role and (re)set its password.

    Roles are cluster-global, so this runs as the migration owner (an admin role)
    rather than being part of any schema. Safe to re-run: it only creates the role
    when absent, then always re-asserts the password (so a rotated secret takes
    effect on the next migration). `pear_app` is a plain, non-privileged login
    role — NOSUPERUSER NOCREATEDB NOCREATEROLE — so it is fully subject to RLS.
    """
    pw = _quote_literal(app_password)
    return f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        CREATE ROLE {APP_ROLE} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE;
    END IF;
END
$$;
ALTER ROLE {APP_ROLE} PASSWORD {pw};
""".strip()


def app_grants_sql(owner_role: str = DEFAULT_OWNER_ROLE) -> str:
    """Return the full GRANT block for `pear_app`, guarded on role existence.

    The Migration agent should `op.execute(app_grants_sql())` once, after the
    tables/functions exist. Idempotent; safe to re-assert across migrations.
    """
    return f"""
DO $$
BEGIN
    IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        -- 1. Schema usage for the app role.
        GRANT USAGE ON SCHEMA public TO {APP_ROLE};

        -- 2. CRUD on existing tables; RLS is the floor, these grants the ceiling.
        GRANT SELECT, INSERT, UPDATE, DELETE
            ON ALL TABLES IN SCHEMA public TO {APP_ROLE};

        -- 3. Sequences for identity columns / gen_random_uuid()-fed defaults.
        GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {APP_ROLE};

        -- 4. Execute on existing functions (e.g. current_user_id,
        --    is_system_mode, is_active_wingperson) so policies can call them.
        GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA public TO {APP_ROLE};

        -- 5. Make the same grants apply to objects created by future
        --    migrations. `FOR ROLE {owner_role}` because that role owns the
        --    objects a migration creates.
        ALTER DEFAULT PRIVILEGES IN SCHEMA public FOR ROLE {owner_role}
            GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO {APP_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public FOR ROLE {owner_role}
            GRANT USAGE, SELECT ON SEQUENCES TO {APP_ROLE};
        ALTER DEFAULT PRIVILEGES IN SCHEMA public FOR ROLE {owner_role}
            GRANT EXECUTE ON FUNCTIONS TO {APP_ROLE};
    END IF;
END
$$;
""".strip()


__all__ = [
    "APP_ROLE",
    "DEFAULT_APP_PASSWORD",
    "DEFAULT_OWNER_ROLE",
    "app_grants_sql",
    "app_role_bootstrap_sql",
]
