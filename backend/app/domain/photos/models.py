"""ProfilePhoto model — a photo on a dater's profile.

Ports `public.profile_photos` from the Supabase schema:
  * 20260228000000_schema.sql          — base table (dating_profile_id, suggester_id,
                                          storage_url, display_order, approved_at)
  * 20260531000000_winger_activity_rejection.sql — adds `rejected_at`

Key deviations from the SQL (per the migration plan):
  * The table's own `id` UUID PK + `created_at` are inherited from BaseDBModel
    (`updated_at` / `deleted_at` are additive and harmless).
  * `suggester_id` is a real FK to profiles.id with `ON DELETE SET NULL`; a null
    value means the photo was self-uploaded by the dater.
  * Photo approval flow: `approved_at` null = pending; `rejected_at` non-null =
    the dater rejected a winger-suggested photo.
  * DB triggers / RLS are not ported here (Phase 4).
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel


class ProfilePhoto(BaseDBModel):
    __tablename__ = "profile_photos"

    # SQL: not null references dating_profiles(id) on delete cascade
    dating_profile_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("dating_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SQL: references profiles(id) on delete set null -- null = self-uploaded
    suggester_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    storage_url: Mapped[str] = mapped_column(sa.Text, nullable=False)
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # null = pending approval
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    # non-null = winger-suggested photo rejected by the dater
    rejected_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # SQL: index on (dating_profile_id, display_order)
        sa.Index(
            "ix_profile_photos_dating_profile_id_display_order",
            "dating_profile_id",
            "display_order",
        ),
        # SQL: index on (suggester_id) where suggester_id is not null
        sa.Index(
            "ix_profile_photos_suggester_id",
            "suggester_id",
            postgresql_where=sa.text("suggester_id IS NOT NULL"),
        ),
    )
