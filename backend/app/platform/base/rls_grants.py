from __future__ import annotations

# Role the migration runner connects as (owns newly-created objects). This is the
# `DB_USER` from `ADMIN_DB_URL`; defaults to `postgres`.
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

    Run `op.execute(app_grants_sql())` once, after the tables/functions exist.
    Idempotent; safe to re-assert across migrations.
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
