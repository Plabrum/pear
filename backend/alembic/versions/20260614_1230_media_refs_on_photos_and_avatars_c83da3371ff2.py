"""media refs on photos and avatars

Revision ID: c83da3371ff2
Revises: b72c92260ee1
Create Date: 2026-06-14 12:30:00.000000+00:00

Points `profile_photos` and `profiles` at the platform `media` table by id instead
of carrying their own S3 keys. `profile_photos.storage_url` becomes `media_id`
(NOT NULL FK -> media.id ON DELETE CASCADE); `profiles.avatar_url` becomes
`avatar_media_id` (nullable FK -> media.id ON DELETE SET NULL). No data to
preserve. Policies are unchanged (this only alters columns), so the RLS set stays
in lockstep with policies-as-code.
"""

from typing import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c83da3371ff2"
down_revision: str | None = "b72c92260ee1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # profile_photos: storage_url (Text key) -> media_id (FK -> media.id).
    op.drop_column("profile_photos", "storage_url")
    op.add_column("profile_photos", sa.Column("media_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_profile_photos_media_id_media",
        "profile_photos",
        "media",
        ["media_id"],
        ["id"],
        ondelete="CASCADE",
    )

    # profiles: avatar_url (Text key) -> avatar_media_id (nullable FK -> media.id).
    op.drop_column("profiles", "avatar_url")
    op.add_column("profiles", sa.Column("avatar_media_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_profiles_avatar_media_id_media",
        "profiles",
        "media",
        ["avatar_media_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_profiles_avatar_media_id_media", "profiles", type_="foreignkey")
    op.drop_column("profiles", "avatar_media_id")
    op.add_column("profiles", sa.Column("avatar_url", sa.Text(), nullable=True))

    op.drop_constraint("fk_profile_photos_media_id_media", "profile_photos", type_="foreignkey")
    op.drop_column("profile_photos", "media_id")
    op.add_column("profile_photos", sa.Column("storage_url", sa.Text(), nullable=False))
