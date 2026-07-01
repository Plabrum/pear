"""Match model — a mutual match between two users.

Ports `public.matches` from 20260228000000_schema.sql:

    user_a_id / user_b_id = the two matched users

Constraints (mirrored from the SQL):
  * unique_match      — UNIQUE (user_a_id, user_b_id)
  * ordered_match_ids — CHECK (user_a_id < user_b_id)

The ordered check enforces user_a_id < user_b_id so the pair is unique regardless
of insertion order — the app must sort the two ids before inserting.

Deviations from the SQL (per the migration plan):
  * `id` UUID PK + `created_at` are inherited from BaseDBModel.
  * FK ondelete semantics mirror the SQL: both ids CASCADE.
  * Matches are created by server-side logic (Phase 5) — no trigger ported here.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel


class Match(BaseDBModel):
    __tablename__ = "matches"

    # SQL: not null references profiles(id) on delete cascade
    user_a_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_b_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        sa.UniqueConstraint("user_a_id", "user_b_id", name="unique_match"),
        sa.CheckConstraint("user_a_id < user_b_id", name="ordered_match_ids"),
    )
