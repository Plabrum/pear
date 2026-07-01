"""media table

Revision ID: b72c92260ee1
Revises: b1c2d3e4f5a6
Create Date: 2026-06-14 12:00:00.000000+00:00

Creates `public.media` (an uploaded object + its processing lifecycle), enables +
forces RLS, and applies media's BESPOKE write policies (NOT the generic
WingpersonScopedMixin FOR ALL policy): INSERT/UPDATE/DELETE are owner + active
wingperson, referencing only `owner_id` so they stand up at table-creation time. The
column-dependent SELECT policy (which references `profile_photos.media_id` and
`profiles.avatar_media_id`) is applied once those columns exist — see the follow-on
RLS revision `d4e5f6a7b8c9`. The policy text is kept in lockstep with
`app/platform/base/rls_policies.py`'s `_MEDIA`, so policies-as-code === migration
SQL (zero autogenerate drift).
"""

from typing import Sequence

import sqlalchemy as sa
from alembic_utils.pg_policy import PGPolicy

from alembic import op
from app.platform.base.rls_grants import app_grants_sql
from app.platform.media.enums import MediaState
from app.utils.textenum import TextEnum

# revision identifiers, used by Alembic.
revision: str = "b72c92260ee1"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MEDIA_INSERT = PGPolicy(
    schema="public",
    signature="media_insert",
    on_entity="public.media",
    definition=(
        "AS PERMISSIVE\n"
        "        FOR INSERT\n"
        "        TO pear_app\n"
        "        WITH CHECK (public.is_system_mode()\n"
        "          OR owner_id = public.current_user_id()\n"
        "          OR public.is_active_wingperson(owner_id))"
    ),
)

_MEDIA_UPDATE = PGPolicy(
    schema="public",
    signature="media_update",
    on_entity="public.media",
    definition=(
        "AS PERMISSIVE\n"
        "        FOR UPDATE\n"
        "        TO pear_app\n"
        "        USING (public.is_system_mode()\n"
        "          OR owner_id = public.current_user_id()\n"
        "          OR public.is_active_wingperson(owner_id))"
    ),
)

_MEDIA_DELETE = PGPolicy(
    schema="public",
    signature="media_delete",
    on_entity="public.media",
    definition=(
        "AS PERMISSIVE\n"
        "        FOR DELETE\n"
        "        TO pear_app\n"
        "        USING (public.is_system_mode()\n"
        "          OR owner_id = public.current_user_id()\n"
        "          OR public.is_active_wingperson(owner_id))"
    ),
)

# SELECT is created in the follow-on RLS revision (after media_id / avatar_media_id
# columns exist); here we only stand up the owner-scoped write policies.
_MEDIA_POLICIES = [_MEDIA_INSERT, _MEDIA_UPDATE, _MEDIA_DELETE]


def upgrade() -> None:
    op.create_table(
        "media",
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("file_key", sa.Text(), nullable=False),
        sa.Column("processed_key", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("state", TextEnum(MediaState), server_default="PENDING", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["profiles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_media_owner_id"), "media", ["owner_id"], unique=False)
    op.create_index(op.f("ix_media_state"), "media", ["state"], unique=False)
    op.create_index(op.f("ix_media_deleted_at"), "media", ["deleted_at"], unique=False)

    for policy in _MEDIA_POLICIES:
        op.create_entity(policy)
    op.enable_rls("public", "media")

    # Re-assert the centralized grants so the new table inherits pear_app CRUD.
    op.execute(app_grants_sql())


def downgrade() -> None:
    op.disable_rls("public", "media")
    for policy in _MEDIA_POLICIES:
        op.drop_entity(policy)
    op.drop_index(op.f("ix_media_deleted_at"), table_name="media")
    op.drop_index(op.f("ix_media_state"), table_name="media")
    op.drop_index(op.f("ix_media_owner_id"), table_name="media")
    op.drop_table("media")
