import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.decisions.enums import DecisionType
from app.platform.base.models import BaseDBModel
from app.utils.sqids import Sqid, SqidType
from app.utils.textenum import TextEnum


class Decision(BaseDBModel):
    __tablename__ = "decisions"

    # SQL: not null references profiles(id) on delete cascade
    actor_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # NULL = wingperson suggestion not yet acted on
    decision: Mapped[DecisionType | None] = mapped_column(TextEnum(DecisionType), nullable=True)
    # the winger who suggested this card — SQL: references profiles(id) on delete set null
    suggested_by: Mapped[Sqid | None] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("actor_id", "recipient_id", name="unique_actor_recipient"),
        sa.CheckConstraint("actor_id <> recipient_id", name="no_self_decision"),
    )
