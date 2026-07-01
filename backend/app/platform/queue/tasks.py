"""Built-in tasks for the queue infrastructure."""

import logging

from app.platform.queue.enums import TaskName
from app.platform.queue.registry import task
from app.platform.queue.types import AppContext

logger = logging.getLogger(__name__)


@task(TaskName.HEALTH_CHECK)
async def health_check(ctx: AppContext, **kwargs: object) -> str:
    """Smoke-test task — confirms the worker is wired up and producing Task rows."""
    logger.info("HEALTH_CHECK task ran")
    return "ok"
