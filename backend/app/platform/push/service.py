from __future__ import annotations

import logging

from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.push.client import BasePushClient
from app.platform.queue.enums import TaskName
from app.platform.queue.transactions import dispatch_task

logger = logging.getLogger(__name__)


class PushService:
    """Per-request push client with log-and-swallow + 410 dead-token reaping."""

    def __init__(self, client: BasePushClient, transaction: AsyncSession, request: Request) -> None:
        self.client = client
        self.transaction = transaction
        self.request = request

    async def send(self, token: str, title: str, body: str) -> None:
        """Deliver one alert push. Never raises; reaps the token on a 410."""
        result = await self.client.send(token, title, body)
        if result.unregistered:
            # Cross-user write — enqueue the SYSTEM-mode reap (runs after commit).
            await dispatch_task(self.transaction, self.request, TaskName.REAP_PUSH_TOKEN, token=token)
