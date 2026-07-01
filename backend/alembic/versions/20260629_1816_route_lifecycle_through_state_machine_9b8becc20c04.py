"""route lifecycle through state machine

Revision ID: 9b8becc20c04
Revises: e74b9f4587a7
Create Date: 2026-06-29 18:16:39.810890+00:00

Every genuine lifecycle/status field becomes a uniform `state` TextEnum column
(StateMachineMixin), driven through the state machine:

  * contacts.wingperson_status -> contacts.state               (rename, same values)
  * decisions.decision (nullable) -> decisions.state            (NULL -> PENDING)
  * profile_photos -> profile_photos.state                      (timestamps -> state)
  * prompt_responses is_approved/is_rejected -> .state          (booleans -> state)
  * profiles.role -> profiles.state                             (the dater|winger mode)
  * dating_profiles.dating_status -> dating_profiles.state      (WINGING folded into role)

"Winging" is unified into the profile role: a dating_profile that was WINGING flips
its owning profile to WINGER and its own status to OPEN.

RLS that referenced the renamed columns (the `is_active_wingperson` function, the
`decisions_insert` / `profile_photos_public_select` / `media_select` policies) is
replaced in lock-step.
"""

from typing import Sequence

import sqlalchemy as sa
from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_policy import PGPolicy

from alembic import op
from app.domain.contacts.enums import WingpersonStatus
from app.domain.dating_profiles.enums import DatingStatus
from app.domain.decisions.enums import DecisionState
from app.domain.photos.enums import PhotoApprovalState
from app.domain.profiles.enums import UserRole
from app.domain.prompts.enums import ApprovalState
from app.utils.textenum import TextEnum

# revision identifiers, used by Alembic.
revision: str = "9b8becc20c04"
down_revision: str | None = "e74b9f4587a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# ── RLS entities (new vs old) ──────────────────────────────────────────────────
NEW_IS_ACTIVE_WINGPERSON = PGFunction(
    schema="public",
    signature="is_active_wingperson(_dater integer)",
    definition=(
        "returns boolean\n        language sql\n        stable\n        security invoker\n"
        "        set search_path = public\n        as $$\n          select exists (\n"
        "            select 1 from public.contacts\n            where user_id = _dater\n"
        "              and winger_id = public.current_user_id()\n"
        "              and state = 'ACTIVE'\n          );\n        $$"
    ),
)
OLD_IS_ACTIVE_WINGPERSON = PGFunction(
    schema="public",
    signature="is_active_wingperson(_dater integer)",
    definition=(
        "returns boolean\n        language sql\n        stable\n        security invoker\n"
        "        set search_path = public\n        as $$\n          select exists (\n"
        "            select 1 from public.contacts\n            where user_id = _dater\n"
        "              and winger_id = public.current_user_id()\n"
        "              and wingperson_status = 'ACTIVE'\n          );\n        $$"
    ),
)

NEW_DECISIONS_INSERT = PGPolicy(
    schema="public",
    signature="decisions_insert",
    on_entity="public.decisions",
    definition=(
        "AS PERMISSIVE\n        FOR INSERT\n        TO pear_app\n"
        "        WITH CHECK (public.is_system_mode() OR (\n"
        "          actor_id = public.current_user_id()\n          OR (\n"
        "            suggested_by = public.current_user_id()\n            AND EXISTS (\n"
        "              SELECT 1 FROM public.contacts c\n"
        "              WHERE c.user_id = decisions.actor_id\n"
        "                AND c.winger_id = public.current_user_id()\n"
        "                AND c.state = 'ACTIVE'\n            )\n          )\n        ))"
    ),
)
OLD_DECISIONS_INSERT = PGPolicy(
    schema="public",
    signature="decisions_insert",
    on_entity="public.decisions",
    definition=(
        "AS PERMISSIVE\n        FOR INSERT\n        TO pear_app\n"
        "        WITH CHECK (public.is_system_mode() OR (\n"
        "          actor_id = public.current_user_id()\n          OR (\n"
        "            suggested_by = public.current_user_id()\n            AND EXISTS (\n"
        "              SELECT 1 FROM public.contacts c\n"
        "              WHERE c.user_id = decisions.actor_id\n"
        "                AND c.winger_id = public.current_user_id()\n"
        "                AND c.wingperson_status = 'ACTIVE'\n            )\n          )\n        ))"
    ),
)

NEW_PHOTOS_PUBLIC_SELECT = PGPolicy(
    schema="public",
    signature="profile_photos_public_select",
    on_entity="public.profile_photos",
    definition=(
        "AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (\n"
        "          profile_photos.suggester_id = public.current_user_id()\n"
        "          OR EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n"
        "            WHERE dp.id = profile_photos.dating_profile_id\n"
        "              AND dp.is_active = true\n"
        "              AND profile_photos.state = 'APPROVED'\n          )\n        )"
    ),
)
OLD_PHOTOS_PUBLIC_SELECT = PGPolicy(
    schema="public",
    signature="profile_photos_public_select",
    on_entity="public.profile_photos",
    definition=(
        "AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n        USING (\n"
        "          profile_photos.suggester_id = public.current_user_id()\n"
        "          OR EXISTS (\n            SELECT 1 FROM public.dating_profiles dp\n"
        "            WHERE dp.id = profile_photos.dating_profile_id\n"
        "              AND dp.is_active = true\n"
        "              AND profile_photos.approved_at IS NOT NULL\n          )\n        )"
    ),
)

NEW_MEDIA_SELECT = PGPolicy(
    schema="public",
    signature="media_select",
    on_entity="public.media",
    definition=(
        "AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n"
        "        USING (public.is_system_mode()\n"
        "          OR owner_id = public.current_user_id()\n"
        "          OR public.is_active_wingperson(owner_id)\n          OR EXISTS (\n"
        "            SELECT 1\n            FROM public.profile_photos pp\n"
        "            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id\n"
        "            WHERE pp.media_id = media.id\n              AND (\n"
        "                dp.user_id = public.current_user_id()\n"
        "                OR pp.suggester_id = public.current_user_id()\n"
        "                OR (dp.is_active = true AND pp.state = 'APPROVED')\n"
        "              )\n          )\n          OR EXISTS (\n"
        "            SELECT 1 FROM public.profiles p WHERE p.avatar_media_id = media.id\n          ))"
    ),
)
OLD_MEDIA_SELECT = PGPolicy(
    schema="public",
    signature="media_select",
    on_entity="public.media",
    definition=(
        "AS PERMISSIVE\n        FOR SELECT\n        TO pear_app\n"
        "        USING (public.is_system_mode()\n"
        "          OR owner_id = public.current_user_id()\n"
        "          OR public.is_active_wingperson(owner_id)\n          OR EXISTS (\n"
        "            SELECT 1\n            FROM public.profile_photos pp\n"
        "            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id\n"
        "            WHERE pp.media_id = media.id\n              AND (\n"
        "                dp.user_id = public.current_user_id()\n"
        "                OR pp.suggester_id = public.current_user_id()\n"
        "                OR (dp.is_active = true AND pp.approved_at IS NOT NULL)\n"
        "              )\n          )\n          OR EXISTS (\n"
        "            SELECT 1 FROM public.profiles p WHERE p.avatar_media_id = media.id\n          ))"
    ),
)


def upgrade() -> None:
    # ── 1. Add the new `state` columns (each NOT NULL with its initial-state default
    #       + the StateMachineMixin index). Existing rows get the default; the
    #       backfill below overrides from the legacy columns. ───────────────────────
    op.add_column(
        "contacts",
        sa.Column("state", TextEnum(WingpersonStatus), server_default="INVITED", nullable=False),
    )
    op.create_index(op.f("ix_contacts_state"), "contacts", ["state"], unique=False)

    op.add_column(
        "decisions",
        sa.Column("state", TextEnum(DecisionState), server_default="PENDING", nullable=False),
    )
    op.create_index(op.f("ix_decisions_state"), "decisions", ["state"], unique=False)

    op.add_column(
        "profile_photos",
        sa.Column("state", TextEnum(PhotoApprovalState), server_default="PENDING", nullable=False),
    )
    op.create_index(op.f("ix_profile_photos_state"), "profile_photos", ["state"], unique=False)

    op.add_column(
        "prompt_responses",
        sa.Column("state", TextEnum(ApprovalState), server_default="PENDING", nullable=False),
    )
    op.create_index(op.f("ix_prompt_responses_state"), "prompt_responses", ["state"], unique=False)

    op.add_column(
        "profiles",
        sa.Column("state", TextEnum(UserRole), server_default="DATER", nullable=False),
    )
    op.create_index(op.f("ix_profiles_state"), "profiles", ["state"], unique=False)

    op.add_column(
        "dating_profiles",
        sa.Column("state", TextEnum(DatingStatus), server_default="OPEN", nullable=False),
    )
    op.create_index(op.f("ix_dating_profiles_state"), "dating_profiles", ["state"], unique=False)

    # ── 2. Backfill `state` from the legacy columns (TextEnum stores `.name`). ──────
    op.execute("UPDATE contacts SET state = wingperson_status")
    op.execute("UPDATE decisions SET state = COALESCE(decision, 'PENDING')")
    op.execute(
        "UPDATE profile_photos SET state = CASE "
        "WHEN rejected_at IS NOT NULL THEN 'REJECTED' "
        "WHEN approved_at IS NOT NULL THEN 'APPROVED' ELSE 'PENDING' END"
    )
    op.execute(
        "UPDATE prompt_responses SET state = CASE "
        "WHEN is_approved THEN 'APPROVED' WHEN is_rejected THEN 'REJECTED' ELSE 'PENDING' END"
    )
    op.execute("UPDATE profiles SET state = role")
    # Unify "winging": a dating_profile that was WINGING means its owner is a winger.
    op.execute(
        "UPDATE profiles p SET state = 'WINGER' "
        "FROM dating_profiles dp WHERE dp.user_id = p.id AND dp.dating_status = 'WINGING'"
    )
    op.execute(
        "UPDATE dating_profiles SET state = CASE WHEN dating_status = 'WINGING' THEN 'OPEN' ELSE dating_status END"
    )

    # ── 3. Re-point the RLS that referenced renamed columns (CREATE OR REPLACE for the
    #       function so its dependent policies survive; drop+create for the policies).
    #       Must run while both old + new columns exist. ───────────────────────────
    op.replace_entity(NEW_IS_ACTIVE_WINGPERSON)
    op.replace_entity(NEW_DECISIONS_INSERT)
    op.replace_entity(NEW_PHOTOS_PUBLIC_SELECT)
    op.replace_entity(NEW_MEDIA_SELECT)

    # ── 4. Drop the legacy columns (nothing references them anymore). ───────────────
    op.drop_column("contacts", "wingperson_status")
    op.drop_column("decisions", "decision")
    op.drop_column("prompt_responses", "is_approved")
    op.drop_column("prompt_responses", "is_rejected")
    op.drop_column("profiles", "role")
    op.drop_column("dating_profiles", "dating_status")


def downgrade() -> None:
    # ── 1. Re-add the legacy columns (nullable/defaulted as before). ───────────────
    op.add_column(
        "contacts",
        sa.Column("wingperson_status", TextEnum(WingpersonStatus), server_default="INVITED", nullable=False),
    )
    op.add_column("decisions", sa.Column("decision", TextEnum(DecisionState), nullable=True))
    op.add_column(
        "prompt_responses",
        sa.Column("is_approved", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "prompt_responses",
        sa.Column("is_rejected", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column(
        "profiles",
        sa.Column("role", TextEnum(UserRole), server_default="DATER", nullable=False),
    )
    op.add_column(
        "dating_profiles",
        sa.Column("dating_status", TextEnum(DatingStatus), server_default="OPEN", nullable=False),
    )

    # ── 2. Backfill legacy columns from `state` (winging history is not recoverable). ──
    op.execute("UPDATE contacts SET wingperson_status = state")
    op.execute("UPDATE decisions SET decision = CASE WHEN state = 'PENDING' THEN NULL ELSE state END")
    op.execute("UPDATE prompt_responses SET is_approved = (state = 'APPROVED'), is_rejected = (state = 'REJECTED')")
    op.execute("UPDATE profiles SET role = state")
    op.execute("UPDATE dating_profiles SET dating_status = state")

    # ── 3. Restore the legacy RLS (references the re-added columns). ────────────────
    op.replace_entity(OLD_IS_ACTIVE_WINGPERSON)
    op.replace_entity(OLD_DECISIONS_INSERT)
    op.replace_entity(OLD_PHOTOS_PUBLIC_SELECT)
    op.replace_entity(OLD_MEDIA_SELECT)

    # ── 4. Drop the `state` columns. ───────────────────────────────────────────────
    op.drop_index(op.f("ix_dating_profiles_state"), table_name="dating_profiles")
    op.drop_column("dating_profiles", "state")
    op.drop_index(op.f("ix_profiles_state"), table_name="profiles")
    op.drop_column("profiles", "state")
    op.drop_index(op.f("ix_prompt_responses_state"), table_name="prompt_responses")
    op.drop_column("prompt_responses", "state")
    op.drop_index(op.f("ix_profile_photos_state"), table_name="profile_photos")
    op.drop_column("profile_photos", "state")
    op.drop_index(op.f("ix_decisions_state"), table_name="decisions")
    op.drop_column("decisions", "state")
    op.drop_index(op.f("ix_contacts_state"), table_name="contacts")
    op.drop_column("contacts", "state")
