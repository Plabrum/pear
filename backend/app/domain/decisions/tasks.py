import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.queries import (
    both_sides_approved,
    find_mutual_match,
    push_tokens_for,
)
from app.domain.matches.models import Match
from app.platform.push.client import build_push_client
from app.platform.queue.enums import TaskName, TaskRoleType
from app.platform.queue.registry import task
from app.platform.queue.transactions import with_transaction
from app.platform.queue.types import AppContext

logger = logging.getLogger(__name__)

MATCH_PUSH_TITLE = "It's a Match! 🎉"
MATCH_PUSH_BODY = "You have a new match. Say hello!"


# NOTE: the function name MUST match TaskName.FORM_MATCH's value ("form_match").
# SAQ identifies tasks by __qualname__, which doubles as the pickle re-import path
# under the `spawn` start method (macOS / Python 3.13). A mismatched name makes the
# task un-picklable and crashes the SAQ worker on startup.
@task(TaskName.FORM_MATCH)
@with_transaction(role_type=TaskRoleType.SYSTEM)
async def form_match(
    ctx: AppContext,
    *,
    transaction: AsyncSession,
    actor_id: str,
    recipient_id: str,
) -> None:
    """Idempotently form the match for a mutually-approved pair, then push both sides.

    Runs under the SYSTEM transaction (`app.is_system_mode = true`), so the
    `matches_insert` RLS policy (`WITH CHECK (public.is_system_mode())`) is
    satisfied here — and ONLY here. The Like action enqueues this after its own
    decision commits; this task re-derives the mutual condition independently:

      * if a match already joins the pair -> nothing to do (idempotent re-run),
      * else if both directions are 'approved' -> insert the ordered matches row
        and notify both users,
      * else -> a no-op (the second approval hasn't landed; the pair's later like
        will enqueue this again).
    """
    a = UUID(actor_id)
    b = UUID(recipient_id)

    if await find_mutual_match(transaction, a, b) is not None:
        return
    if not await both_sides_approved(transaction, a, b):
        return

    lo, hi = (a, b) if str(a) < str(b) else (b, a)
    match = Match(user_a_id=lo, user_b_id=hi)
    transaction.add(match)
    await transaction.flush()

    # Worker-injected client (set at queue startup); build one if absent (sync dispatch).
    push_client = ctx.get("push_client") or build_push_client(ctx["config"])
    tokens = await push_tokens_for(transaction, [lo, hi])
    for token in tokens:
        await push_client.send(token, MATCH_PUSH_TITLE, MATCH_PUSH_BODY)
