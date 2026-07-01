import logging
from datetime import UTC, datetime
from typing import cast

from litestar_saq import QueueConfig
from saq.job import Status
from saq.types import Context, ReceivesContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import config
from app.platform.comms.clients.email import LocalEmailClient, SESEmailClient
from app.platform.push.client import build_push_client
from app.platform.queue.enums import TaskStatus
from app.platform.queue.models import Task
from app.platform.queue.registry import get_registry
from app.platform.queue.types import AppContext
from app.utils.discovery import discover_and_import

logger = logging.getLogger(__name__)

_SAQ_STATUS_MAP: dict[Status, TaskStatus] = {
    Status.COMPLETE: TaskStatus.COMPLETE,
    Status.FAILED: TaskStatus.FAILED,
    Status.ABORTED: TaskStatus.ABORTED,
    Status.ABORTING: TaskStatus.ABORTED,
}


async def queue_startup(ctx: AppContext) -> None:  # type: ignore[override]
    """SAQ startup hook — inject shared resources into the task context.

    Pear's queue only needs a DB sessionmaker and an email client; the LocalEmailClient
    logs instead of sending in dev.
    """
    engine = create_async_engine(
        config.ASYNC_DATABASE_URL,
        pool_size=0,  # no persistent connections — tasks are short-lived
        max_overflow=5,
    )
    ctx["db_engine"] = engine
    ctx["db_sessionmaker"] = async_sessionmaker(engine, expire_on_commit=False)
    ctx["config"] = config
    ctx["queue"] = ctx["worker"].queue
    ctx["email_client"] = LocalEmailClient() if config.IS_DEV else SESEmailClient(config)
    # Direct-APNs push client (LocalPushClient in dev/test or when APNs creds are
    # absent) — used by the fan-out SEND_PUSH task. The 1:1 inline sends from
    # actions use the request-scoped client instead.
    ctx["push_client"] = build_push_client(config)
    logger.info("Queue worker started — DB sessionmaker, email & push clients injected into context")


async def queue_shutdown(ctx: AppContext) -> None:  # type: ignore[override]
    """SAQ shutdown hook — dispose DB engine."""
    engine = ctx.get("db_engine")
    if engine is not None:
        await engine.dispose()
    logger.info("Queue worker stopped — DB engine disposed")


async def before_process(ctx: Context) -> None:
    """Upsert a Task row with status=ACTIVE when a job starts."""
    job = ctx.get("job")
    if job is None:
        return
    sessionmaker: async_sessionmaker = ctx["db_sessionmaker"]  # type: ignore[assignment]
    now = datetime.now(UTC)
    async with sessionmaker() as session:
        result = await session.execute(select(Task).where(Task.job_key == job.key))
        task = result.scalar_one_or_none()
        if task is None:
            task = Task(
                job_key=job.key,
                queue=job.queue.name if job.queue else "default",
                task_name=job.function,
                status=TaskStatus.ACTIVE,
                started_at=now,
            )
            session.add(task)
        else:
            task.status = TaskStatus.ACTIVE
            task.started_at = now
        await session.commit()


async def after_process(ctx: Context) -> None:
    """Update the Task row with final status and completed_at after a job finishes."""
    job = ctx.get("job")
    if job is None:
        return
    sessionmaker: async_sessionmaker = ctx["db_sessionmaker"]  # type: ignore[assignment]
    now = datetime.now(UTC)
    final_status = _SAQ_STATUS_MAP.get(job.status, TaskStatus.COMPLETE)
    error_text = job.error if job.error else None
    async with sessionmaker() as session:
        result = await session.execute(select(Task).where(Task.job_key == job.key))
        task = result.scalar_one_or_none()
        if task is None:
            task = Task(
                job_key=job.key,
                queue=job.queue.name if job.queue else "default",
                task_name=job.function,
                status=final_status,
                completed_at=now,
                error=error_text,
            )
            session.add(task)
        else:
            task.status = final_status
            task.completed_at = now
            task.error = error_text
        await session.commit()


# Trigger @task / @scheduled_task decorator registration across all tasks.py files
discover_and_import(["tasks.py"], base_path="app")

registry = get_registry()


def get_queue_config() -> list[QueueConfig]:
    return [
        QueueConfig(
            name="default",
            dsn=config.REDIS_URL,
            tasks=registry.get_all_tasks(),
            scheduled_tasks=registry.get_all_scheduled_tasks(),  # type: ignore[reportArgumentType]
            cron_tz=UTC,
            startup=cast(ReceivesContext, queue_startup),
            shutdown=cast(ReceivesContext, queue_shutdown),
            before_process=cast(ReceivesContext, before_process),
            after_process=cast(ReceivesContext, after_process),
            concurrency=10,
            shutdown_grace_period_s=0 if config.IS_DEV else 30,
        )
    ]


queue_config = get_queue_config()
