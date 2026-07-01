"""Typed AppContext for SAQ tasks."""

from typing import Required

from saq.queue import Queue
from saq.types import Context
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Config
from app.platform.comms.clients.email import BaseEmailClient


class AppContext(Context):
    db_engine: Required[AsyncEngine]
    db_sessionmaker: Required[async_sessionmaker[AsyncSession]]
    config: Required[Config]
    queue: Required[Queue]
    email_client: Required[BaseEmailClient]
