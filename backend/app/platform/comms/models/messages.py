"""Outbound email message model (queued → SES).

Pear's comms platform is outbound-only: there is no inbound parsing, no SES
webhook, and no EmailThread/Message threading. A row is created QUEUED by
``EmailService`` and transitioned to SENT/FAILED by the ``SEND_EMAIL`` task.

``user_id`` is a soft reference to the sending/recipient user. It is intentionally
NOT a DB foreign key in this phase — the user/profile tables land in Phase 3, and
the relationship-aware RLS policies that would scope this table land in Phase 4.
"""

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.comms.enums import MessageDirection, MessageState
from app.utils.textenum import TextEnum


class Message(BaseDBModel):
    __tablename__ = "email_messages"

    user_id: Mapped[UUID | None] = mapped_column(sa.Uuid, index=True)
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
