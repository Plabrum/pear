import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.base.rls import MutualMatchInsert, Participants, RLSScopedMixin
from app.utils.sqids import Sqid, SqidType


# Participant-only read. INSERT is gated by `MutualMatchInsert`: a participant may
# form the pair's match in-request, but ONLY when both directions of their decision
# are 'approved' — RLS rejects any forged (non-mutual) pairing.
class Match(
    BaseDBModel,
    RLSScopedMixin(read=Participants("user_a_id", "user_b_id"), edit={"INSERT": MutualMatchInsert()}),
):
    __tablename__ = "matches"

    # SQL: not null references profiles(id) on delete cascade
    user_a_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_b_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        sa.UniqueConstraint("user_a_id", "user_b_id", name="unique_match"),
        sa.CheckConstraint("user_a_id < user_b_id", name="ordered_match_ids"),
    )
