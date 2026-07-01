import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.queries import push_tokens_for
from app.platform.push.client import build_push_client
from app.platform.queue.enums import TaskName, TaskRoleType
from app.platform.queue.registry import task
from app.platform.queue.transactions import with_transaction
from app.platform.queue.types import AppContext
from app.utils.sqids import Sqid

logger = logging.getLogger(__name__)

MATCH_PUSH_TITLE = "It's a Match! 🎉"
MATCH_PUSH_BODY = "You have a new match. Say hello!"


# NOTE: the function name MUST match TaskName.NOTIFY_MATCH's value ("notify_match").
# SAQ identifies tasks by __qualname__, which doubles as the pickle re-import path
# under the `spawn` start method (macOS / Python 3.13). A mismatched name makes the
# task un-picklable and crashes the SAQ worker on startup.
@task(TaskName.NOTIFY_MATCH)
@with_transaction(role_type=TaskRoleType.SYSTEM)
async def notify_match(
    ctx: AppContext,
    *,
    transaction: AsyncSession,
    user_a_id: Sqid,
    user_b_id: Sqid,
) -> None:
    """Push the "It's a Match!" notification to both sides of a freshly-formed match.

    The match row itself is created in-request by the Like action (gated by the
    `matches_insert` RLS floor); this task only fans the push out, keeping the
    direct-APNs sends off the request hot path. Enqueued exactly once — by the like
    that actually formed the row — so there's no double-send to guard against.

    Runs under the SYSTEM transaction so it can read both users' push tokens
    regardless of the actor scope.
    """
    # Worker-injected client (set at queue startup); build one if absent (sync dispatch).
    push_client = ctx.get("push_client") or build_push_client(ctx["config"])
    tokens = await push_tokens_for(transaction, [user_a_id, user_b_id])
    for token in tokens:
        await push_client.send(token, MATCH_PUSH_TITLE, MATCH_PUSH_BODY)
