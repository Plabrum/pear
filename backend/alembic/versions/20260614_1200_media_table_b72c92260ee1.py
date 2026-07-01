"""media table

Revision ID: b72c92260ee1
Revises: b1c2d3e4f5a6
Create Date: 2026-06-14 12:00:00.000000+00:00

Creates `public.media` (an uploaded object + its processing lifecycle), enables +
forces RLS, and applies the WingpersonScopedMixin policy (owner + active wingperson
+ system). The policy SQL is generated from the mixin helper so it stays in lockstep
with `app/platform/base/rls_mixins.py` (policies-as-code === migration, zero drift).
"""

from typing import Sequence

import sqlalchemy as sa
from alembic_utils.pg_policy import PGPolicy

from alembic import op
from app.platform.base.rls_grants import app_grants_sql
from app.platform.base.rls_mixins import _wingperson_scoped_definition
from app.platform.media.enums import MediaState
from app.utils.textenum import TextEnum

# revision identifiers, used by Alembic.
revision: str = "b72c92260ee1"
down_revision: str | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MEDIA_POLICY = PGPolicy(
    schema="public",
    signature="wingperson_scope_policy",
    on_entity="public.media",
    definition=_wingperson_scoped_definition("owner_id").strip(),
)


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

    op.create_entity(_MEDIA_POLICY)
    op.enable_rls("public", "media")

    # Re-assert the centralized grants so the new table inherits pear_app CRUD.
    op.execute(app_grants_sql())


def downgrade() -> None:
    op.disable_rls("public", "media")
    op.drop_entity(_MEDIA_POLICY)
    op.drop_index(op.f("ix_media_deleted_at"), table_name="media")
    op.drop_index(op.f("ix_media_state"), table_name="media")
    op.drop_index(op.f("ix_media_owner_id"), table_name="media")
    op.drop_table("media")
