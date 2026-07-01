import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.push.queries import null_push_token
from app.platform.queue.enums import TaskName, TaskRoleType
from app.platform.queue.registry import task
from app.platform.queue.transactions import with_transaction
from app.platform.queue.types import AppContext

logger = logging.getLogger(__name__)


@task(TaskName.REAP_PUSH_TOKEN)
@with_transaction(role_type=TaskRoleType.SYSTEM)
async def reap_push_token(
    ctx: AppContext,
    *,
    transaction: AsyncSession,
    token: str,
) -> None:
    """Null a dead push token (APNs 410 Unregistered) across all profiles."""
    cleared = await null_push_token(transaction, token)
    logger.info("Reaped dead push token (%d profile(s) cleared)", cleared)


@task(TaskName.SEND_PUSH)
@with_transaction(role_type=TaskRoleType.SYSTEM)
async def send_push(
    ctx: AppContext,
    *,
    transaction: AsyncSession,
    tokens: list[str],
    title: str,
    body: str,
) -> None:
    """Fan-out an alert push to many device tokens; reap any 410s inline.

    Log-and-swallow per token: one bad token never stalls the batch (the client's
    ``send`` already swallows transport errors and returns a result).
    """
    push_client = ctx["push_client"]
    for token in tokens:
        result = await push_client.send(token, title, body)
        if result.unregistered:
            await null_push_token(transaction, token)
