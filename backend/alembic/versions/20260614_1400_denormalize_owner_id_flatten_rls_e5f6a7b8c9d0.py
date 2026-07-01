"""denormalize owner_id; flatten rls

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-14 14:00:00.000000+00:00

Denormalizes the owning dater onto profile_photos / profile_prompts (owner_id) and
prompt_responses (profile_owner_id, distinct from the author's user_id), so RLS and
the action ownership checks become flat column compares instead of EXISTS joins
through dating_profiles. The columns are added NOT NULL with no default: the tables
are empty (no prod data; the test DB seeds rows AFTER migrating), so no backfill is
needed.

The relationship-scoped write policies on profile_photos / profile_prompts are
replaced by the reusable RLS mixin floors (WingpersonScopedMixin / UserScopedMixin,
keyed on the new owner_id) plus one supplementary public-SELECT policy each (approved
photos / active-profile prompts that discover & matches read cross-user). The
prompt_responses select/update policies are rewritten onto the flat
profile_owner_id. alembic_utils does not diff policy DEFINITIONS, so the policy churn
is hand-written here; the literals are kept in lockstep with
app/platform/base/rls_policies.py and rls_mixins.py (policies-as-code === migration
SQL).
"""

from typing import Sequence

import sqlalchemy as sa
from alembic_utils.pg_policy import PGPolicy

from alembic import op
from app.platform.base.rls_grants import app_grants_sql

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: str | None = "d4e5f6a7b8c9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── OLD bespoke policies (dropped on upgrade) ────────────────────────────────────
_OLD_PHOTOS_SELECT = PGPolicy(
    schema="public",
    signature="profile_photos_select",
    on_entity="public.profile_photos",
    definition="AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_photos.dating_profile_id\n              AND (\n                dp.user_id = public.current_user_id()\n                OR profile_photos.suggester_id = public.current_user_id()\n                OR (dp.is_active = true AND profile_photos.approved_at IS NOT NULL)\n              )\n          )\n        ))",
)
_OLD_PHOTOS_INSERT = PGPolicy(
    schema="public",
    signature="profile_photos_insert",
    on_entity="public.profile_photos",
    definition="AS PERMISSIVE\n        FOR INSERT\n        TO pear_app\n        WITH CHECK (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_photos.dating_profile_id\n              AND (\n                dp.user_id = public.current_user_id()\n                OR (\n                  profile_photos.suggester_id = public.current_user_id()\n                  AND public.is_active_wingperson(dp.user_id)\n                )\n              )\n          )\n        ))",
)
_OLD_PHOTOS_UPDATE = PGPolicy(
    schema="public",
    signature="profile_photos_update",
    on_entity="public.profile_photos",
    definition="AS PERMISSIVE\n        FOR UPDATE\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_photos.dating_profile_id\n              AND dp.user_id = public.current_user_id()\n          )\n        ))",
)
_OLD_PHOTOS_DELETE = PGPolicy(
    schema="public",
    signature="profile_photos_delete",
    on_entity="public.profile_photos",
    definition="AS PERMISSIVE\n        FOR DELETE\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_photos.dating_profile_id\n              AND dp.user_id = public.current_user_id()\n          )\n          OR profile_photos.suggester_id = public.current_user_id()\n        ))",
)

_OLD_PROMPTS_SELECT = PGPolicy(
    schema="public",
    signature="profile_prompts_select",
    on_entity="public.profile_prompts",
    definition="AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_prompts.dating_profile_id\n              AND (dp.is_active = true OR dp.user_id = public.current_user_id())\n          )\n        ))",
)
_OLD_PROMPTS_INSERT = PGPolicy(
    schema="public",
    signature="profile_prompts_insert",
    on_entity="public.profile_prompts",
    definition="AS PERMISSIVE\n        FOR INSERT\n        TO pear_app\n        WITH CHECK (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_prompts.dating_profile_id\n              AND dp.user_id = public.current_user_id()\n          )\n        ))",
)
_OLD_PROMPTS_UPDATE = PGPolicy(
    schema="public",
    signature="profile_prompts_update",
    on_entity="public.profile_prompts",
    definition="AS PERMISSIVE\n        FOR UPDATE\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_prompts.dating_profile_id\n              AND dp.user_id = public.current_user_id()\n          )\n        ))",
)
_OLD_PROMPTS_DELETE = PGPolicy(
    schema="public",
    signature="profile_prompts_delete",
    on_entity="public.profile_prompts",
    definition="AS PERMISSIVE\n        FOR DELETE\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_prompts.dating_profile_id\n              AND dp.user_id = public.current_user_id()\n          )\n        ))",
)

_OLD_RESPONSES_SELECT = PGPolicy(
    schema="public",
    signature="prompt_responses_select",
    on_entity="public.prompt_responses",
    definition="AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          user_id = public.current_user_id()\n          OR EXISTS (\n            SELECT 1\n            FROM public.profile_prompts pp\n            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id\n            WHERE pp.id = prompt_responses.profile_prompt_id\n              AND dp.user_id = public.current_user_id()\n          )\n        ))",
)
_OLD_RESPONSES_UPDATE = PGPolicy(
    schema="public",
    signature="prompt_responses_update",
    on_entity="public.prompt_responses",
    definition="AS PERMISSIVE\n        FOR UPDATE\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          EXISTS (\n            SELECT 1\n            FROM public.profile_prompts pp\n            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id\n            WHERE pp.id = prompt_responses.profile_prompt_id\n              AND dp.user_id = public.current_user_id()\n          )\n        ))",
)

_OLD_POLICIES = [
    _OLD_PHOTOS_SELECT,
    _OLD_PHOTOS_INSERT,
    _OLD_PHOTOS_UPDATE,
    _OLD_PHOTOS_DELETE,
    _OLD_PROMPTS_SELECT,
    _OLD_PROMPTS_INSERT,
    _OLD_PROMPTS_UPDATE,
    _OLD_PROMPTS_DELETE,
    _OLD_RESPONSES_SELECT,
    _OLD_RESPONSES_UPDATE,
]


# ── NEW policies (created on upgrade) ────────────────────────────────────────────
# Mixin floors — kept byte-for-byte in lockstep with rls_mixins.py's generated text.
_PHOTOS_FLOOR = PGPolicy(
    schema="public",
    signature="wingperson_scope_policy",
    on_entity="public.profile_photos",
    definition="AS PERMISSIVE\n        FOR ALL\n        TO pear_app\n        USING (public.is_system_mode() OR owner_id = public.current_user_id() OR public.is_active_wingperson(owner_id))\n        WITH CHECK (public.is_system_mode() OR owner_id = public.current_user_id() OR public.is_active_wingperson(owner_id))",
)
_PROMPTS_FLOOR = PGPolicy(
    schema="public",
    signature="user_scope_policy",
    on_entity="public.profile_prompts",
    definition="AS PERMISSIVE\n        FOR ALL\n        TO pear_app\n        USING (public.is_system_mode() OR owner_id = public.current_user_id())\n        WITH CHECK (public.is_system_mode() OR owner_id = public.current_user_id())",
)

# Supplementary public selects + rewritten flat response policies — in lockstep with
# rls_policies.py.
_PHOTOS_PUBLIC_SELECT = PGPolicy(
    schema="public",
    signature="profile_photos_public_select",
    on_entity="public.profile_photos",
    definition="AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (\n          profile_photos.suggester_id = public.current_user_id()\n          OR EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_photos.dating_profile_id\n              AND dp.is_active = true\n              AND profile_photos.approved_at IS NOT NULL\n          )\n        )",
)
_PROMPTS_PUBLIC_SELECT = PGPolicy(
    schema="public",
    signature="profile_prompts_public_select",
    on_entity="public.profile_prompts",
    definition="AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (\n          EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n            WHERE dp.id = profile_prompts.dating_profile_id\n              AND dp.is_active = true\n          )\n        )",
)
_NEW_RESPONSES_SELECT = PGPolicy(
    schema="public",
    signature="prompt_responses_select",
    on_entity="public.prompt_responses",
    definition="AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (public.is_system_mode() OR (\n          user_id = public.current_user_id()\n          OR profile_owner_id = public.current_user_id()\n        ))",
)
_NEW_RESPONSES_UPDATE = PGPolicy(
    schema="public",
    signature="prompt_responses_update",
    on_entity="public.prompt_responses",
    definition="AS PERMISSIVE\n        FOR UPDATE\n        TO pear_app\n        USING (public.is_system_mode() OR (profile_owner_id = public.current_user_id()))",
)

_NEW_POLICIES = [
    _PHOTOS_FLOOR,
    _PROMPTS_FLOOR,
    _PHOTOS_PUBLIC_SELECT,
    _PROMPTS_PUBLIC_SELECT,
    _NEW_RESPONSES_SELECT,
    _NEW_RESPONSES_UPDATE,
]


def upgrade() -> None:
    # ── Denormalized owner columns (NOT NULL FK, empty tables → no backfill) ──
    op.add_column("profile_photos", sa.Column("owner_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_profile_photos_owner_id_profiles",
        "profile_photos",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_profile_photos_owner_id", "profile_photos", ["owner_id"])

    op.add_column("profile_prompts", sa.Column("owner_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_profile_prompts_owner_id_profiles",
        "profile_prompts",
        "profiles",
        ["owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_profile_prompts_owner_id", "profile_prompts", ["owner_id"])

    op.add_column("prompt_responses", sa.Column("profile_owner_id", sa.Uuid(), nullable=False))
    op.create_foreign_key(
        "fk_prompt_responses_profile_owner_id_profiles",
        "prompt_responses",
        "profiles",
        ["profile_owner_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_prompt_responses_profile_owner_id", "prompt_responses", ["profile_owner_id"])

    # ── Policy churn: drop the join-based bespoke policies, install the flat
    #    mixin floors + supplementary selects + rewritten response policies. ──
    for policy in _OLD_POLICIES:
        op.drop_entity(policy)
    for policy in _NEW_POLICIES:
        op.create_entity(policy)

    # Re-assert the centralized grants (idempotent) so the floors inherit pear_app CRUD.
    op.execute(app_grants_sql())


def downgrade() -> None:
    for policy in _NEW_POLICIES:
        op.drop_entity(policy)
    for policy in _OLD_POLICIES:
        op.create_entity(policy)

    op.drop_index("ix_prompt_responses_profile_owner_id", table_name="prompt_responses")
    op.drop_constraint("fk_prompt_responses_profile_owner_id_profiles", "prompt_responses", type_="foreignkey")
    op.drop_column("prompt_responses", "profile_owner_id")

    op.drop_index("ix_profile_prompts_owner_id", table_name="profile_prompts")
    op.drop_constraint("fk_profile_prompts_owner_id_profiles", "profile_prompts", type_="foreignkey")
    op.drop_column("profile_prompts", "owner_id")

    op.drop_index("ix_profile_photos_owner_id", table_name="profile_photos")
    op.drop_constraint("fk_profile_photos_owner_id_profiles", "profile_photos", type_="foreignkey")
    op.drop_column("profile_photos", "owner_id")

    op.execute(app_grants_sql())
