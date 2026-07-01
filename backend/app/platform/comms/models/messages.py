from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.comms.enums import MessageDirection, MessageState
from app.utils.sqids import Sqid, SqidType
from app.utils.textenum import TextEnum


class Message(BaseDBModel):
    """Outbound email message. Created QUEUED by ``EmailService`` and transitioned
    to SENT/FAILED by the ``SEND_EMAIL`` task. Outbound-only — no inbound parsing
    or threading."""

    __tablename__ = "email_messages"

    # Soft reference to the sending/recipient user; intentionally not a DB foreign key.
    user_id: Mapped[Sqid | None] = mapped_column(SqidType, index=True)
    direction: Mapped[MessageDirection] = mapped_column(TextEnum(MessageDirection), nullable=False)
    state: Mapped[MessageState] = mapped_column(TextEnum(MessageState), nullable=False)

    subject: Mapped[str | None] = mapped_column(sa.Text)
    body_text: Mapped[str | None] = mapped_column(sa.Text)
    body_html: Mapped[str | None] = mapped_column(sa.Text)
    from_email: Mapped[str | None] = mapped_column(sa.Text)
    from_name: Mapped[str | None] = mapped_column(sa.Text)
    to_emails: Mapped[list[str]] = mapped_column(sa.ARRAY(sa.Text), server_default="{}")
    reply_to_email: Mapped[str | None] = mapped_column(sa.Text)
    template_name: Mapped[str | None] = mapped_column(sa.Text)

    ses_message_id: Mapped[str | None] = mapped_column(sa.Text, unique=True, index=True)
    sent_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(sa.Text)
