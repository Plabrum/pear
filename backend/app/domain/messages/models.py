import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.base.rls import Owner, RLSScopedMixin, ViaMatch
from app.utils.sqids import Sqid, SqidType


# Read only within a match you participate in. INSERT is sender-owned (match
# participation on send is enforced by the SendMessage action's is_available).
# UPDATE is match-participant-scoped, not sender-owned: marking a message read is
# done by its *recipient*, not its sender.
class Message(
    BaseDBModel,
    RLSScopedMixin(
        read=ViaMatch("match_id"),
        edit={"INSERT": Owner("sender_id"), "UPDATE": ViaMatch("match_id")},
    ),
):
    __tablename__ = "messages"

    # SQL: not null references matches(id) on delete cascade
    # The composite (match_id, created_at) index below covers match_id-prefix
    # lookups, so no standalone index here.
    match_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SQL: not null references profiles(id) on delete cascade
    sender_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())

    __table_args__ = (sa.Index("ix_messages_match_id_created_at", "match_id", "created_at"),)
