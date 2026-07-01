"""Mutations for the messages domain — all writes live here as registered actions.

Ported from the POST handlers in
`supabase/functions/api/domains/messages/route.ts`:

  * `SendMessage`       (POST /matches/{matchId}/messages)      -> BaseObjectAction[Match, SendMessageData]
  * `MarkMessagesRead`  (POST /matches/{matchId}/messages/read) -> BaseObjectAction[Match, EmptyActionData]

Both act ON A MATCH: the action route's `object_id` is the match id, the group's
`model_type` is `Match`, so the framework loads the match (RLS-scoped) and gates each
action via `is_available(match, deps)` — the viewer must be a party to the match.
This reproduces the Hono `isViewerInMatch` 404 (a non-party match is invisible under
RLS, so `get_object` returns None and the framework raises NotFound; a visible match
the viewer is somehow not on is denied by `is_available`).

Messages have no status workflow (no approval / lifecycle enum), so there is NO
state machine for this domain — `is_read` is a plain boolean flipped in bulk by the
mark-read action, mirroring the Hono `UPDATE ... SET is_read = true`.

Each `execute` mutates the ORM directly under the request's RLS-scoped transaction;
the action machinery commits on return and rolls back on raise. User-facing failures
are raised as typed `ApplicationError` subclasses (never ad-hoc responses).

Registration: imported at boot by `discover_and_import(["actions.py", ...],
base_path="app/domain")`, which runs `action_group_factory(...)` to register the
group + decorates each action class into the singleton `ActionRegistry`. The
`ActionGroupType.MESSAGE_ACTIONS` member is added to `app.platform.actions.enums` by
the Integrate stage; this module imports it from there.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.matches.models import Match
from app.domain.messages.queries import (
    fetch_push_token,
    get_match_peers,
    insert_message,
    mark_messages_read,
)
from app.domain.messages.schemas import SendMessageData
from app.platform.actions.base import (
    BaseObjectAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse

# ── Action group ──────────────────────────────────────────────────────────────

message_actions = action_group_factory(
    ActionGroupType.MESSAGE_ACTIONS,
    default_invalidation="messages",
    model_type=Match,
)


def _viewer_in_match(match: Match, deps: ActionDeps) -> bool:
    """The actor must be one of the two matched users."""
    return deps.user.id in (match.user_a_id, match.user_b_id)


# ── POST /matches/{matchId}/messages ──────────────────────────────────────────


@message_actions
class SendMessage(BaseObjectAction[Match, SendMessageData]):
    action_key = "send"  # type: ignore[assignment]
    label = "Send Message"
    icon = ActionIcon.SEND

    @classmethod
    def is_available(cls, obj: Match, deps: ActionDeps) -> bool:
        return _viewer_in_match(obj, deps)

    @classmethod
    async def execute(
        cls,
        obj: Match,
        data: SendMessageData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        viewer_id = deps.user.id
        row = await insert_message(transaction, obj.id, viewer_id, data.body)

        # Push the recipient: "New message from <name>: <preview>".
        peers = await get_match_peers(transaction, obj.id)
        if peers is not None:
            user_a_id, user_b_id = peers
            recipient_id = user_b_id if user_a_id == viewer_id else user_a_id
            recipient_token = await fetch_push_token(transaction, recipient_id)
            if recipient_token is not None:
                sender_name = row.sender_chosen_name or "Someone"
                preview = data.body if len(data.body) <= 80 else data.body[:77] + "…"
                await deps.push.send(recipient_token, f"New message from {sender_name}", preview)

        # TODO(Phase 6): broadcast the new message over the realtime channel so the
        # recipient's open conversation updates live (Supabase Realtime today).

        return ActionExecutionResponse(
            message="Message sent",
            invalidate_queries=["messages", "conversations"],
            created_id=row.id,
        )


# ── POST /matches/{matchId}/messages/read ─────────────────────────────────────


@message_actions
class MarkMessagesRead(BaseObjectAction[Match, EmptyActionData]):
    action_key = "mark_read"  # type: ignore[assignment]
    label = "Mark Read"
    icon = ActionIcon.CHECK

    @classmethod
    def is_available(cls, obj: Match, deps: ActionDeps) -> bool:
        return _viewer_in_match(obj, deps)

    @classmethod
    async def execute(
        cls,
        obj: Match,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        updated = await mark_messages_read(transaction, obj.id, deps.user.id)
        return ActionExecutionResponse(
            message=f"Marked {updated} message(s) read",
            invalidate_queries=["messages", "conversations"],
        )
