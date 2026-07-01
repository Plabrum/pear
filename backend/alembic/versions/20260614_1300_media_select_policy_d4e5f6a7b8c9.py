"""media select policy

Revision ID: d4e5f6a7b8c9
Revises: c83da3371ff2
Create Date: 2026-06-14 13:00:00.000000+00:00

Adds the bespoke `media_select` policy now that `profile_photos.media_id` and
`profiles.avatar_media_id` exist (revision c83da3371ff2). It mirrors profile_photos
visibility EXACTLY so a viewer reads a media row iff they may see a photo backing it
(owner, the photo's suggester, or an approved photo on an active dating profile),
plus public-read avatars. A matched viewer therefore presigns an approved photo's
URL under their OWN scope — no system mode. The policy text is kept in lockstep with
`app/platform/base/rls_policies.py`'s `_MEDIA` (media_select), so policies-as-code
=== migration SQL (zero autogenerate drift).
"""

from typing import Sequence

from alembic_utils.pg_policy import PGPolicy

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c83da3371ff2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MEDIA_SELECT = PGPolicy(
    schema="public",
    signature="media_select",
    on_entity="public.media",
    definition=(
        "AS PERMISSIVE\n"
        "        FOR SELECT\n"
        "        TO pear_app\n"
        "        USING (public.is_system_mode()\n"
        "          OR owner_id = public.current_user_id()\n"
        "          OR public.is_active_wingperson(owner_id)\n"
        "          OR EXISTS (\n"
        "            SELECT 1\n"
        "            FROM public.profile_photos pp\n"
        "            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id\n"
        "            WHERE pp.media_id = media.id\n"
        "              AND (\n"
        "                dp.user_id = public.current_user_id()\n"
        "                OR pp.suggester_id = public.current_user_id()\n"
        "                OR (dp.is_active = true AND pp.approved_at IS NOT NULL)\n"
        "              )\n"
        "          )\n"
        "          OR EXISTS (\n"
        "            SELECT 1 FROM public.profiles p WHERE p.avatar_media_id = media.id\n"
        "          ))"
    ),
)


def upgrade() -> None:
    op.create_entity(_MEDIA_SELECT)


def downgrade() -> None:
    op.drop_entity(_MEDIA_SELECT)
