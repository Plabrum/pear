from __future__ import annotations

from enum import StrEnum
from typing import ClassVar
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.exceptions import (
    CannotSuggestSelfError,
    NotActiveWingpersonError,
)
from app.domain.dating_profiles.models import DatingProfile
from app.domain.dating_profiles.schemas import ReportActionData, SuggestActionData
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.queries import (
    both_sides_approved,
    dater_push_and_winger_name,
    find_mutual_match,
    insert_wing_suggestion,
    is_active_wingperson,
    upsert_direct_decision,
)
from app.domain.decisions.schemas import fields_set
from app.domain.reports.queries import insert_report, upsert_decline_decision
from app.platform.actions.base import (
    BaseObjectAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from app.platform.queue.enums import TaskName
from app.platform.queue.transactions import dispatch_task
from app.platform.state_machine.roles import Role

SUGGESTION_PUSH_TITLE = "New profile suggestion 👀"


async def _is_fresh_mutual(transaction: AsyncSession, user_a: UUID, user_b: UUID) -> bool:
    """True when the pair just became mutually approved and no match exists yet.

    Read under the caller's OWN RLS scope: the Like actor is the actor of
    (me -> target) and the recipient of (target -> me), so `decisions_select`
    exposes both directions; `matches_select` exposes any existing pair match. This
    is purely the client-overlay signal — the match row itself is formed by the
    FORM_MATCH task (system mode), never in this request.
    """
    if await find_mutual_match(transaction, user_a, user_b) is not None:
        return False
    return await both_sides_approved(transaction, user_a, user_b)


# ── Action keys + group ────────────────────────────────────────────────────────


class DatingProfileActionKey(StrEnum):
    LIKE = "like"
    PASS = "pass"
    SUGGEST = "suggest"
    REPORT = "report"


dating_profile_swipe_actions = action_group_factory(
    ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS,
    default_invalidation="dating_profiles",
    model_type=DatingProfile,
)


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (like) ─────────


@dating_profile_swipe_actions
class Like(BaseObjectAction[DatingProfile, EmptyActionData]):
    """A dater likes the target dating profile (upsert approved + match signal).

    Absorbs the former act-on-suggestion path: the upsert lands on the winger's
    pending row when one exists (preserving `suggested_by`), else creates a fresh
    row. Match formation itself is deferred to the FORM_MATCH task (system mode);
    this action only enqueues it and reports the overlay signal to the client.
    """

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.LIKE
    label = "Like"
    icon = ActionIcon.HEART

    @classmethod
    def is_available(cls, obj: DatingProfile, deps: ActionDeps) -> bool:
        # Only a dater swipes, and never on their own profile.
        return deps.user.role is Role.DATER and obj.user_id != deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        actor_id = deps.user.id
        recipient_id = obj.user_id
        # Upsert the actor's OWN decision under their RLS scope (lands on a winger's
        # pending row when one exists, preserving `suggested_by`).
        await upsert_direct_decision(transaction, actor_id, recipient_id, DecisionType.APPROVED)

        # Detect mutual under the actor's OWN scope purely for the client overlay
        # signal; the match row is formed by the FORM_MATCH task (system mode),
        # enqueued after this decision commits so the task sees it.
        fresh_match = await _is_fresh_mutual(transaction, actor_id, recipient_id)
        if fresh_match:
            await dispatch_task(
                transaction,
                deps.request,
                TaskName.FORM_MATCH,
                actor_id=str(actor_id),
                recipient_id=str(recipient_id),
            )
        return ActionExecutionResponse(
            message="It's a match!" if fresh_match else "Liked",
            invalidate_queries=["decisions", "matches", "dating_profiles"],
            # Non-null => the client shows the match overlay. The real match id is
            # not known here (the task creates the row); a sentinel preserves the
            # existing `created_id != null` contract without forging a match row.
            created_id=uuid4() if fresh_match else None,
        )


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (pass) ─────────


@dating_profile_swipe_actions
class Pass(BaseObjectAction[DatingProfile, EmptyActionData]):
    """A dater passes on the target dating profile (upsert declined)."""

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.PASS
    label = "Pass"
    icon = ActionIcon.X

    @classmethod
    def is_available(cls, obj: DatingProfile, deps: ActionDeps) -> bool:
        return deps.user.role is Role.DATER and obj.user_id != deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await upsert_direct_decision(transaction, deps.user.id, obj.user_id, DecisionType.DECLINED)
        return ActionExecutionResponse(
            message="Passed",
            invalidate_queries=["decisions", "dating_profiles"],
        )


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (suggest) ──────


@dating_profile_swipe_actions
class Suggest(BaseObjectAction[DatingProfile, SuggestActionData]):
    """A winger suggests the target dating profile to one of their daters.

    `is_available` gates the synchronous part (the viewer is a winger). The
    active-wingperson relationship depends on `data.daterId`, which `is_available`
    cannot see and which needs an async lookup, so it is enforced in `execute`
    (raising 403) and additionally by the decisions INSERT RLS policy.
    """

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.SUGGEST
    label = "Suggest"
    icon = ActionIcon.SEND

    @classmethod
    def is_available(cls, obj: DatingProfile, deps: ActionDeps) -> bool:
        return deps.user.role is Role.WINGER and obj.user_id != deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: SuggestActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        winger_id = deps.user.id
        recipient_id = obj.user_id
        if data.daterId == recipient_id:
            raise CannotSuggestSelfError()

        if not await is_active_wingperson(transaction, data.daterId, winger_id):
            raise NotActiveWingpersonError()

        provided = fields_set(data)
        note = provided.get("note") if "note" in provided else None
        inserted = await insert_wing_suggestion(
            transaction,
            data.daterId,
            recipient_id,
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


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (report) ───────


@dating_profile_swipe_actions
class Report(BaseObjectAction[DatingProfile, ReportActionData]):
    """File a report against the target dating profile's owner.

    Two effects, matching the former FileReport: insert the `profile_reports` row,
    and upsert a `declined` decision so the reported profile leaves the reporter's
    swipe queue.
    """

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.REPORT
    label = "Report"
    icon = ActionIcon.BLOCK

    @classmethod
    def is_available(cls, obj: DatingProfile, deps: ActionDeps) -> bool:
        # Any viewer may report; never your own profile.
        return obj.user_id != deps.user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: ReportActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        reporter_id = deps.user.id
        reported_id = obj.user_id
        await insert_report(transaction, reporter_id, reported_id, data.reason)
        await upsert_decline_decision(transaction, reporter_id, reported_id)
        return ActionExecutionResponse(
            message="Report filed",
            invalidate_queries=["reports", "decisions", "dating_profiles"],
        )
