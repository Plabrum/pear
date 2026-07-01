"""Custom Alembic operations for Row-Level Security management.

Usage in migrations:
    op.enable_rls('public', 'profiles')
    op.disable_rls('public', 'profiles')
"""

from __future__ import annotations

from alembic.autogenerate import renderers
from alembic.operations import MigrateOperation, Operations


class EnableRLSOp(MigrateOperation):
    """Operation to enable Row-Level Security on a table."""

    def __init__(self, schema: str, tablename: str, force: bool = True):
        self.schema = schema
        self.tablename = tablename
        self.force = force

    def reverse(self):
        return DisableRLSOp(self.schema, self.tablename)


class DisableRLSOp(MigrateOperation):
    """Operation to disable Row-Level Security on a table."""

    def __init__(self, schema: str, tablename: str):
        self.schema = schema
        self.tablename = tablename

    def reverse(self):
        return EnableRLSOp(self.schema, self.tablename, force=True)


# Implementation functions
def _impl_enable_rls(operations, operation):
    operations.execute(f"ALTER TABLE {operation.schema}.{operation.tablename} ENABLE ROW LEVEL SECURITY")
    if operation.force:
        operations.execute(f"ALTER TABLE {operation.schema}.{operation.tablename} FORCE ROW LEVEL SECURITY")


def _impl_disable_rls(operations, operation):
    operations.execute(f"ALTER TABLE {operation.schema}.{operation.tablename} NO FORCE ROW LEVEL SECURITY")
    operations.execute(f"ALTER TABLE {operation.schema}.{operation.tablename} DISABLE ROW LEVEL SECURITY")


# Register implementations
Operations.implementation_for(EnableRLSOp)(_impl_enable_rls)
Operations.implementation_for(DisableRLSOp)(_impl_disable_rls)


# Add convenience methods to Operations class
def enable_rls(self, schema: str, tablename: str, force: bool = True):
    op = EnableRLSOp(schema, tablename, force)
    return self.invoke(op)


def disable_rls(self, schema: str, tablename: str):
    op = DisableRLSOp(schema, tablename)
    return self.invoke(op)


Operations.enable_rls = enable_rls  # type: ignore[attr-defined]
Operations.disable_rls = disable_rls  # type: ignore[attr-defined]


@renderers.dispatch_for(EnableRLSOp)
def render_enable_rls(autogen_context, op):
    force_param = f", force={op.force}" if not op.force else ""
    return f"op.enable_rls('{op.schema}', '{op.tablename}'{force_param})"


@renderers.dispatch_for(DisableRLSOp)
def render_disable_rls(autogen_context, op):
    return f"op.disable_rls('{op.schema}', '{op.tablename}')"
