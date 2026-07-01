from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel


class Message(BaseDBModel):
    __tablename__ = "messages"

    # SQL: not null references matches(id) on delete cascade
    match_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SQL: not null references profiles(id) on delete cascade
    sender_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    body: Mapped[str] = mapped_column(sa.Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False, server_default=sa.false())
