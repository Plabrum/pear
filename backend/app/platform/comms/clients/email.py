import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aioboto3

from app.config import Config
from app.platform.queue.exceptions import CommittableTaskError

logger = logging.getLogger(__name__)


class EmailSendError(CommittableTaskError):
    """Raised when an email client fails to deliver a message."""


@dataclass
class EmailPayload:
    """Email payload passed to the underlying client."""

    to: list[str]
    subject: str
    body_html: str
    body_text: str
    from_email: str
    from_name: str | None = None
    reply_to: str | None = None
    message_id: str | None = None


class BaseEmailClient(ABC):
    @abstractmethod
    async def send_email(self, message: EmailPayload) -> str:
        """Send an email. Returns the provider's message ID."""


class LocalEmailClient(BaseEmailClient):
    """Logs the email instead of sending — used for dev and tests."""

    async def send_email(self, message: EmailPayload) -> str:
        from_header = f'"{message.from_name}" <{message.from_email}>' if message.from_name else message.from_email

        logger.info("=" * 80)
        logger.info("LOCAL EMAIL (not actually sent)")
        logger.info(f"To: {', '.join(message.to)}")
        logger.info(f"From: {from_header}")
        logger.info(f"Subject: {message.subject}")
        logger.info(f"Reply-To: {message.reply_to}")
        logger.info(f"Message-ID: {message.message_id}")
        logger.info("-" * 80)
        logger.info("Text Body")
        logger.info(message.body_text)
        logger.info("=" * 80)

        return f"local-{uuid.uuid4()}"


class SESEmailClient(BaseEmailClient):
    """AWS SES email client (async)."""

    def __init__(self, config: Config):
        self.region = config.SES_REGION
        self.configuration_set = config.SES_CONFIGURATION_SET

    async def send_email(self, message: EmailPayload) -> str:
        session = aioboto3.Session()

        async with session.client("ses", region_name=self.region) as ses:  # type: ignore[attr-defined]
            from_header = f'"{message.from_name}" <{message.from_email}>' if message.from_name else message.from_email

            msg = MIMEMultipart("alternative")
            msg["Subject"] = message.subject
            msg["From"] = from_header
            msg["To"] = ", ".join(message.to)

            if message.message_id:
                msg["Message-ID"] = message.message_id

            if message.reply_to:
                msg["Reply-To"] = message.reply_to

            msg.attach(MIMEText(message.body_text, "plain", "utf-8"))
            msg.attach(MIMEText(message.body_html, "html", "utf-8"))

            kwargs: dict = {
                "Source": message.from_email,
                "Destinations": message.to,
                "RawMessage": {"Data": msg.as_string()},
            }

            if self.configuration_set:
                kwargs["ConfigurationSetName"] = self.configuration_set

            response = await ses.send_raw_email(**kwargs)
            logger.info(f"Email sent via SES: {response['MessageId']}")
            return response["MessageId"]
