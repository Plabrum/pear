from typing import Required

from saq.queue import Queue
from saq.types import Context
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.config import Config
from app.platform.comms.clients.email import BaseEmailClient
from app.platform.media.client import BaseMediaClient
from app.platform.push.client import BasePushClient


class AppContext(Context):
    db_engine: Required[AsyncEngine]
    db_sessionmaker: Required[async_sessionmaker[AsyncSession]]
    config: Required[Config]
    queue: Required[Queue]
    email_client: Required[BaseEmailClient]
    push_client: Required[BasePushClient]
    media_client: Required[BaseMediaClient]
