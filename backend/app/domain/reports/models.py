"""ProfileReport model — a user reporting another user's profile.

Ports `public.profile_reports` from 20260512000000_profile_reports.sql.

Deviations from the SQL (per the migration plan):
  * `id` UUID PK + `created_at` are inherited from BaseDBModel (the SQL declared
    them ad-hoc; `updated_at`/`deleted_at` are additive and harmless).
  * The SQL's FKs point at `auth.users(id)`; here both `reporter_id` and
    `reported_id` retarget the relocated identity anchor `profiles.id`, keeping
    the SQL's `on delete cascade`.
  * The "Users can insert their own reports" RLS policy is NOT ported (Phase 4).
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.profiles.models import Profile
from app.platform.base.models import BaseDBModel


class ProfileReport(BaseDBModel):
    __tablename__ = "profile_reports"

    # SQL: reporter_id uuid not null references auth.users(id) on delete cascade
    reporter_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SQL: reported_id uuid not null references auth.users(id) on delete cascade
    reported_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)

    reporter: Mapped[Profile] = relationship(
        Profile,
        foreign_keys=[reporter_id],
        lazy="raise",
    )
    reported: Mapped[Profile] = relationship(
        Profile,
        foreign_keys=[reported_id],
        lazy="raise",
    )
