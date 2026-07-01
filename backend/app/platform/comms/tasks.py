"""Comms async tasks — outbound email only."""

import logging
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.comms.clients.email import BaseEmailClient, EmailPayload, EmailSendError
from app.platform.comms.enums import MessageState
from app.platform.comms.models.messages import Message
from app.platform.queue.enums import TaskName
from app.platform.queue.registry import task
from app.platform.queue.transactions import with_transaction
from app.platform.queue.types import AppContext

logger = logging.getLogger(__name__)


# NOTE: the function name MUST match TaskName.SEND_EMAIL's value ("send_email").
# SAQ identifies tasks by __qualname__, which doubles as the pickle re-import path
# under the `spawn` start method (macOS / Python 3.13). A mismatched name makes the
# task un-picklable and crashes the SAQ worker on startup.
@task(TaskName.SEND_EMAIL)
@with_transaction
async def send_email(
    ctx: AppContext,
    *,
    transaction: AsyncSession,
    email_client: BaseEmailClient,
    message_id: str,
) -> None:
    """Send a queued outbound message and transition it to SENT/FAILED.

    ``message_id`` arrives as a UUID string (enqueued via dispatch_task). On
    delivery failure the row is marked FAILED and an EmailSendError is raised —
    a CommittableTaskError, so the FAILED state commits before the retry surfaces.
    """
    record = await transaction.get(Message, UUID(message_id))
    if record is None:
        raise ValueError(f"Message {message_id} not found")

    payload = EmailPayload(
        to=record.to_emails,
        subject=record.subject or "",
        body_html=record.body_html or "",
        body_text=record.body_text or "",
        from_email=record.from_email or "",
        from_name=record.from_name,
        reply_to=record.reply_to_email,
    )

    try:
        ses_id = await email_client.send_email(payload)
        record.ses_message_id = ses_id
        record.sent_at = datetime.now(UTC)
        record.state = MessageState.SENT
    except Exception as e:
        record.error_message = str(e)
        record.state = MessageState.FAILED
        raise EmailSendError(str(e)) from e
