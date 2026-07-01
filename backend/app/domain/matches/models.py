import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.utils.sqids import Sqid, SqidType


class Match(BaseDBModel):
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
