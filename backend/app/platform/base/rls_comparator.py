"""Alembic comparator for detecting RLS state changes.

Checks whether tables that should have RLS actually have it enabled,
and generates migrations to enable/disable RLS as needed.
"""

from __future__ import annotations

from sqlalchemy import text

from app.platform.base.rls_operations import DisableRLSOp, EnableRLSOp


def compare_rls(
    autogen_context,
    upgrade_ops,
    schema,
    tablename,
    metadata_table,
    *args,
    **kwargs,
):
    if metadata_table is None:
        return

    schema = schema or "public"

    # Check metadata: should this table have RLS?
    rls_tables = autogen_context.metadata.info.get("rls", set())
    should_have_rls = tablename in rls_tables

    # Check database: does this table currently have RLS enabled?
    connection = autogen_context.connection
    result = connection.execute(
        text(
            """
            SELECT t.rowsecurity::boolean as rls_enabled,
                   c.relforcerowsecurity::boolean as force_rls
            FROM pg_tables t
            JOIN pg_class c ON c.relname = t.tablename
            JOIN pg_namespace n ON n.oid = c.relnamespace AND n.nspname = t.schemaname
            WHERE t.schemaname = :schema
              AND t.tablename = :tablename
        """
        ),
        {"schema": schema, "tablename": tablename},
    )

    row = result.fetchone()
    has_rls = row and row[0]
    has_force_rls = row and row[1]

    if should_have_rls and not has_rls:
        upgrade_ops.ops.append(EnableRLSOp(schema, tablename, force=True))
    elif has_rls and not should_have_rls:
        upgrade_ops.ops.append(DisableRLSOp(schema, tablename))
    elif should_have_rls and has_rls and not has_force_rls:
        upgrade_ops.ops.append(DisableRLSOp(schema, tablename))
        upgrade_ops.ops.append(EnableRLSOp(schema, tablename, force=True))
