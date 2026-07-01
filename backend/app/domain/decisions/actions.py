"""Mutations for the decisions domain — all writes live here as registered actions.

Ported from the POST handlers in
`supabase/functions/api/domains/decisions/route.ts`:

  * `RecordDirectDecision` (POST /decisions)                -> BaseTopLevelAction
  * `ActOnSuggestion`      (POST /decisions/suggestions/act) -> BaseTopLevelAction
  * `CreateSuggestion`     (POST /decisions/suggestions)     -> BaseTopLevelAction

All three are TOP-LEVEL actions: they key off the (actor, recipient) composite, not
a single object_id, so there is no row to load up front (Hono upserts/inserts by
composite too). Each `execute` mutates the ORM directly under the request's
RLS-scoped transaction; the action machinery commits on return and rolls back on
raise. User-facing failures are raised as typed `ApplicationError` subclasses,
reproducing the Hono `HTTPException` status codes — never ad-hoc responses.

MATCH FORMATION (the legacy `create_match_if_mutual` trigger): when a decision
results in BOTH directions being 'approved', `_finalize_match` creates the matches
row under the honored system-mode escape (the `matches_insert WITH CHECK
is_system_mode()` policy) and fires the match push to both users. This keeps the
mutual-match side-effect in one declarative place, as the Hono route did inline.

The match-formation flow is NOT modeled as a `StateMachineService` transition:
neither `Decision` nor `Match` carries a status column (`state` attribute) the
platform `StateMachine` requires — match creation is an INSERT under system mode,
not a status move on an existing row. Role-gating instead lives on the actions
themselves (a dater's direct decision vs. a winger's suggestion are distinct
actions), and on the decisions RLS INSERT policy.

Registration: imported at boot by `discover_and_import([...], base_path="app/domain")`,
which runs `action_group_factory(...)` to register the group and decorates each
action class into the singleton `ActionRegistry`. The
`ActionGroupType.DECISION_ACTIONS` member is added to `app.platform.actions.enums`
by the Integrate stage.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.exceptions import (
    CannotDecideOnSelfError,
    CannotSuggestSelfError,
    NoPendingSuggestionError,
    NotActiveWingpersonError,
)
from app.domain.decisions.models import Decision
from app.domain.decisions.queries import (
    act_on_pending_suggestion,
    both_sides_approved,
    create_match_system,
    dater_push_and_winger_name,
    find_mutual_match,
    insert_wing_suggestion,
    is_active_wingperson,
    push_tokens_for,
    upsert_direct_decision,
)
from app.domain.decisions.schemas import (
    ActSuggestionData,
    DirectDecisionData,
    SuggestData,
    fields_set,
)
from app.domain.matches.models import Match
from app.platform.actions.base import BaseTopLevelAction, action_group_factory
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse

MATCH_PUSH_TITLE = "It's a Match! 🎉"
MATCH_PUSH_BODY = "You have a new match. Say hello!"

SUGGESTION_PUSH_TITLE = "New profile suggestion 👀"


async def _push_match_created(
    transaction: AsyncSession,
    deps: ActionDeps,
    user_a: UUID,
    user_b: UUID,
) -> None:
    tokens = await push_tokens_for(transaction, [user_a, user_b])
    for token in tokens:
        await deps.push.send(token, MATCH_PUSH_TITLE, MATCH_PUSH_BODY)


async def _finalize_match(
    transaction: AsyncSession,
    deps: ActionDeps,
    user_a: UUID,
    user_b: UUID,
) -> tuple[bool, Match | None]:
    """Create the match if both sides approved and it doesn't exist yet.

    Returns (created, match). `created` is True only when this call inserted a new
    matches row (mirrors Hono's `matchBefore == null && matchAfter != null`). Fires
    the match push to both users on creation.
    """
    existing = await find_mutual_match(transaction, user_a, user_b)
    if existing is not None:
        return False, existing
    if not await both_sides_approved(transaction, user_a, user_b):
        return False, None
    match = await create_match_system(transaction, user_a, user_b)
    await _push_match_created(transaction, deps, match.user_a_id, match.user_b_id)
    return True, match


# ── Action group ───────────────────────────────────────────────────────────────

decision_actions = action_group_factory(
    ActionGroupType.DECISION_ACTIONS,
    default_invalidation="decisions",
    model_type=Decision,
)


# ── POST /decisions ──────────────────────────────────────────────────────────────


@decision_actions
class RecordDirectDecision(BaseTopLevelAction[DirectDecisionData]):
    """A dater's own like/pass on a recipient (direct decision; upsert)."""

    action_key = "record"  # type: ignore[assignment]
    label = "Decide"
    icon = ActionIcon.HEART

    @classmethod
    async def execute(
        cls,
        data: DirectDecisionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        actor_id = deps.user.id
        if actor_id == data.recipientId:
            raise CannotDecideOnSelfError()

        await upsert_direct_decision(transaction, actor_id, data.recipientId, data.decision)
        created, match = await _finalize_match(transaction, deps, actor_id, data.recipientId)

        return ActionExecutionResponse(
            message="It's a match!" if created else "Decision recorded",
            invalidate_queries=["decisions", "matches", "discover"],
            created_id=match.id if (created and match is not None) else None,
        )


# ── POST /decisions/suggestions/act ──────────────────────────────────────────────


@decision_actions
class ActOnSuggestion(BaseTopLevelAction[ActSuggestionData]):
    """Approve/decline a winger's pending suggestion (dater acts on their feed)."""

    action_key = "act_suggestion"  # type: ignore[assignment]
    label = "Act on Suggestion"
    icon = ActionIcon.CHECK

    @classmethod
    async def execute(
        cls,
        data: ActSuggestionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        actor_id = deps.user.id
        updated = await act_on_pending_suggestion(transaction, actor_id, data.recipientId, data.decision)
        if not updated:
            raise NoPendingSuggestionError()

        _, match = await _finalize_match(transaction, deps, actor_id, data.recipientId)

        return ActionExecutionResponse(
            message="It's a match!" if match is not None else "Suggestion acted on",
            invalidate_queries=["decisions", "matches", "discover"],
            created_id=match.id if match is not None else None,
        )


# ── POST /decisions/suggestions ──────────────────────────────────────────────────


@decision_actions
class CreateSuggestion(BaseTopLevelAction[SuggestData]):
    """A winger creates a suggestion on the dater's behalf.

    Gated to active wingpeople: `is_available` can't see the body's `daterId`, so
    the relationship check runs in `execute` (raising 403) and is additionally
    enforced by the decisions INSERT RLS policy.
    """

    action_key = "create_suggestion"  # type: ignore[assignment]
    label = "Suggest Profile"
    icon = ActionIcon.SEND

    @classmethod
    async def execute(
        cls,
        data: SuggestData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        winger_id = deps.user.id
        if data.daterId == data.recipientId:
            raise CannotSuggestSelfError()

        allowed = await is_active_wingperson(transaction, data.daterId, winger_id)
        if not allowed:
            raise NotActiveWingpersonError()

        provided = fields_set(data)
        note = provided.get("note") if "note" in provided else None
        inserted = await insert_wing_suggestion(
            transaction,
            data.daterId,
            data.recipientId,
            winger_id,
            note,  # type: ignore[arg-type]
            data.decision,
        )

        # Only notify on a genuinely new suggestion the dater must act on — a no-op
        # conflict (already decided / already suggested) must not fire a push, and a
        # 'declined' suggestion bypasses the dater entirely.
        if inserted and data.decision is None:
            dater_token, winger_name = await dater_push_and_winger_name(transaction, data.daterId, winger_id)
            if dater_token is not None:
                await deps.push.send(
                    dater_token,
                    SUGGESTION_PUSH_TITLE,
                    f"{winger_name or 'Your wingperson'} suggested a profile for you to check out.",
                )

        return ActionExecutionResponse(
            message="Suggestion created",
            invalidate_queries=["decisions", "pending-suggestions"],
        )
