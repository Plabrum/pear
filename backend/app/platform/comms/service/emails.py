import logging
from typing import Any
from uuid import UUID

from email_validator import EmailNotValidError, validate_email
from litestar import Request
from litestar.plugins.jinja import JinjaTemplateEngine
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.platform.comms.enums import MessageDirection, MessageState
from app.platform.comms.models.messages import Message
from app.platform.queue.enums import TaskName
from app.platform.queue.transactions import dispatch_task

logger = logging.getLogger(__name__)


class EmailService:
    """High-level email service: validates addresses, renders templates, persists
    a Message row, and enqueues the SEND_EMAIL task after commit."""

    def __init__(self, template_engine: JinjaTemplateEngine, transaction: AsyncSession, request: Request):
        self.template_engine = template_engine
        self.transaction = transaction
        self.request = request

    def validate_email_address(self, email: str) -> str:
        try:
            valid = validate_email(email, check_deliverability=False)
            return valid.normalized
        except EmailNotValidError as e:
            raise ValueError(f"Invalid email address: {email}") from e

    def render_template(self, template_name: str, context: dict[str, Any]) -> tuple[str, str]:
        """Render email template, returning (html, text).

        Templates live under EMAIL_TEMPLATES_DIR as
        ``<name>/html.jinja2`` + ``<name>/text.jinja2``.
        """
        jinja_env = self.template_engine.engine
        html_body = jinja_env.get_template(f"{template_name}/html.jinja2").render(**context)
        text_body = jinja_env.get_template(f"{template_name}/text.jinja2").render(**context)
        return html_body, text_body

    async def send_email(
        self,
        *,
        to: list[str] | str,
        subject: str,
        template_name: str,
        context: dict[str, Any],
        user_id: UUID | None = None,
        from_email: str | None = None,
        from_name: str | None = None,
        reply_to: str | None = None,
    ) -> UUID:
        if isinstance(to, str):
            to = [to]
        to = [self.validate_email_address(email) for email in to]

        from_email = from_email or config.EMAIL_FROM

        html_body, text_body = self.render_template(template_name, context)

        record = Message(
            user_id=user_id,
            direction=MessageDirection.OUT,
            state=MessageState.QUEUED,
            to_emails=to,
            from_email=from_email,
            from_name=from_name,
            reply_to_email=reply_to,
            subject=subject,
            body_html=html_body,
            body_text=text_body,
            template_name=template_name,
        )
        self.transaction.add(record)
        await self.transaction.flush()

        await dispatch_task(self.transaction, self.request, TaskName.SEND_EMAIL, message_id=str(record.id))
        return record.id

    async def send_magic_link_email(
        self,
        *,
        to_email: str,
        magic_link_url: str,
        user_id: UUID | None = None,
        expires_minutes: int = 15,
    ) -> UUID:
        return await self.send_email(
            user_id=user_id,
            to=to_email,
            subject="Sign in to Pear",
            template_name="magic_link",
            context={
                "magic_link_url": magic_link_url,
                "expiration_minutes": expires_minutes,
            },
        )
