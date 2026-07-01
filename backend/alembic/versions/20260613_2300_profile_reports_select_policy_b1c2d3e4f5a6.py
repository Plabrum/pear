"""profile_reports select policy

Phase 5, reports domain port. The Phase-4 RLS layer gave `public.profile_reports`
only an INSERT policy (the Hono/Supabase original needed no more — PostgREST
returned nothing on insert). The SQLAlchemy ORM, however, emits
`INSERT ... RETURNING created_at, updated_at` for the BaseDBModel server-side
defaults, and under FORCE RLS that RETURNING read requires a SELECT policy. Without
one, Postgres rejects the insert as "new row violates row-level security policy for
table profile_reports".

This migration adds the matching SELECT policy: a reporter may read back their own
reports (mirrors `decisions_select`'s actor scoping, plus the system-mode escape).
The policy text is kept in lockstep with `app/platform/base/rls_policies.py`'s
`_PROFILE_REPORTS`.

Revision ID: b1c2d3e4f5a6
Revises: 4a5166053ba0
Create Date: 2026-06-13 23:00:00.000000+00:00
"""

from typing import Sequence

from alembic_utils.pg_policy import PGPolicy

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b1c2d3e4f5a6"
down_revision: str | None = "4a5166053ba0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_PROFILE_REPORTS_SELECT = PGPolicy(
    schema="public",
    signature="profile_reports_select",
    on_entity="public.profile_reports",
    definition=(
        "AS PERMISSIVE\n"
        "        FOR SELECT\n"
        "        TO pear_app\n"
        "        USING (public.is_system_mode() OR (reporter_id = public.current_user_id()))"
    ),
)


def upgrade() -> None:
    op.create_entity(_PROFILE_REPORTS_SELECT)


def downgrade() -> None:
    op.drop_entity(_PROFILE_REPORTS_SELECT)
