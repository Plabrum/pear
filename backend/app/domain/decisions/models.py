"""Decision model — swipes (likes/passes) and wingperson suggestions.

Ports `public.decisions` from 20260228000000_schema.sql:

    actor_id     = the dater the decision belongs to
    recipient_id = the profile being decided on
    decision     = approved | declined | NULL (NULL = pending wingperson suggestion)
    suggested_by = the winger who suggested this card (nullable)
    note         = optional message from the wingperson shown in Discover (nullable)

Constraints (mirrored from the SQL):
  * unique_actor_recipient — UNIQUE (actor_id, recipient_id)
  * no_self_decision       — CHECK (actor_id <> recipient_id)

Deviations from the SQL (per the migration plan):
  * `id` UUID PK + `created_at` are inherited from BaseDBModel.
  * `decision` is TEXT via `TextEnum`, not a Postgres native enum; the column is
    nullable (Mapped[DecisionType | None]) — NULL = a suggestion not yet acted on.
  * FK ondelete semantics mirror the SQL: actor_id / recipient_id CASCADE,
    suggested_by SET NULL.
  * The create_match_if_mutual trigger is NOT ported (Phase 5).
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.decisions.enums import DecisionType
from app.platform.base.models import BaseDBModel
from app.utils.textenum import TextEnum


class Decision(BaseDBModel):
    __tablename__ = "decisions"

    # SQL: not null references profiles(id) on delete cascade
    actor_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL = wingperson suggestion not yet acted on
    decision: Mapped[DecisionType | None] = mapped_column(TextEnum(DecisionType), nullable=True)
    # the winger who suggested this card — SQL: references profiles(id) on delete set null
    suggested_by: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("actor_id", "recipient_id", name="unique_actor_recipient"),
        sa.CheckConstraint("actor_id <> recipient_id", name="no_self_decision"),
    )
