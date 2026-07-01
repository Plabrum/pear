import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.utils.sqids import Sqid, SqidType


class Message(BaseDBModel):
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
