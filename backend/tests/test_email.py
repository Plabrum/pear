import logging
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from litestar.plugins.jinja import JinjaTemplateEngine
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.platform.comms.clients.email import EmailPayload, LocalEmailClient
from app.platform.comms.enums import MessageDirection, MessageState
from app.platform.comms.models.messages import Message
from app.platform.comms.service.emails import EmailService
from app.platform.queue.enums import TaskName


def _email_service(transaction: AsyncSession) -> tuple[EmailService, MagicMock]:
    """EmailService wired to the real Jinja engine + a mock request."""
    engine = JinjaTemplateEngine(directory=config.EMAIL_TEMPLATES_DIR)
    request = MagicMock()
    return EmailService(template_engine=engine, transaction=transaction, request=request), request


async def test_send_magic_link_renders_and_enqueues(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict = {}

    async def fake_dispatch(transaction, request, task_name, *, queue="default", **kwargs):
        captured["task_name"] = task_name
        captured["kwargs"] = kwargs

    # Patch the symbol imported into the emails module.
    monkeypatch.setattr("app.platform.comms.service.emails.dispatch_task", fake_dispatch)

    service, _ = _email_service(db_session)
    user_id = uuid4()

    message_id = await service.send_magic_link_email(
        to_email="dater@example.com",
        magic_link_url="https://pear.local/auth/magic?token=abc123",
        user_id=user_id,
    )

    # A QUEUED Message row was persisted with rendered bodies.
    row = (await db_session.execute(select(Message).where(Message.id == message_id))).scalar_one()
    assert row.direction == MessageDirection.OUT
    assert row.state == MessageState.QUEUED
    assert row.to_emails == ["dater@example.com"]
    assert row.template_name == "magic_link"
    assert row.subject == "Sign in to Pear"
    assert row.user_id == user_id
    assert row.body_html and "abc123" in row.body_html
    assert row.body_text and "abc123" in row.body_text

    # The SEND_EMAIL task was dispatched with the message id (as a UUID string).
    assert captured["task_name"] == TaskName.SEND_EMAIL
    assert UUID(captured["kwargs"]["message_id"]) == message_id


async def test_send_email_validates_address(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.platform.comms.service.emails.dispatch_task", AsyncMock())
    service, _ = _email_service(db_session)

    with pytest.raises(ValueError, match="Invalid email address"):
        await service.send_email(
            to="not-an-email",
            subject="x",
            template_name="magic_link",
            context={"magic_link_url": "u", "expiration_minutes": 15},
        )


async def test_local_email_client_logs(caplog: pytest.LogCaptureFixture) -> None:
    client = LocalEmailClient()
    payload = EmailPayload(
        to=["winger@example.com"],
        subject="Hello from Pear",
        body_html="<p>hi</p>",
        body_text="hi",
        from_email="noreply@pear.local",
    )

    with caplog.at_level(logging.INFO, logger="app.platform.comms.clients.email"):
        provider_id = await client.send_email(payload)

    assert provider_id.startswith("local-")
    log_text = "\n".join(r.getMessage() for r in caplog.records)
    assert "LOCAL EMAIL (not actually sent)" in log_text
    assert "winger@example.com" in log_text
    assert "Hello from Pear" in log_text
