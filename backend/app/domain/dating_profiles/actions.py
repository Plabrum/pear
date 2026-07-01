from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.exceptions import CannotSuggestSelfError
from app.domain.dating_profiles.models import DatingProfile
from app.domain.dating_profiles.schemas import (
    DeclineForDaterData,
    ReportActionData,
    SuggestActionData,
)
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.queries import (
    apply_dater_decision,
    dater_push_and_winger_name,
    form_match_if_mutual,
    insert_wing_suggestion,
)
from app.domain.reports.queries import insert_report
from app.platform.actions.base import (
    BaseObjectAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from app.platform.auth.principal import User
from app.platform.queue.enums import TaskName
from app.platform.queue.transactions import dispatch_task
from app.platform.state_machine.roles import Role

SUGGESTION_PUSH_TITLE = "New profile suggestion 👀"


# ── Action keys + group ────────────────────────────────────────────────────────


class DatingProfileActionKey(StrEnum):
    LIKE = "like"
    PASS = "pass"
    SUGGEST = "suggest"
    DECLINE = "decline"
    REPORT = "report"


dating_profile_swipe_actions = action_group_factory(
    ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS,
    default_invalidation="/dating-profiles/swipe",
    model_type=DatingProfile,
)


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (like) ─────────


@dating_profile_swipe_actions
class Like(BaseObjectAction[DatingProfile, EmptyActionData]):
    """A dater likes the target dating profile (upsert approved + form match).

    Absorbs the former act-on-suggestion path: the upsert lands on the winger's
    pending row when one exists (preserving `suggested_by`), else creates a fresh
    row. When the like completes a mutual pair the match row is formed IN-REQUEST
    (gated by the `matches_insert` RLS floor), so the action returns the real match
    id; the "It's a Match!" push is enqueued (off the request hot path).
    """

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.LIKE
    label = "Like"
    icon = ActionIcon.HEART

    @classmethod
    def is_available(cls, obj: DatingProfile, user: User, deps: ActionDeps) -> bool:
        # Only a dater swipes, and never on their own profile.
        return user.role is Role.DATER and obj.user_id != user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        actor_id = user.id
        recipient_id = obj.user_id
        # Apply the actor's OWN decision under their RLS scope (transitions a winger's
        # pending row when one exists, preserving `suggested_by`; else creates it).
        await apply_dater_decision(transaction, deps.state_machine_service, user, recipient_id, DecisionState.APPROVED)

        # Form the match in-request via the guarded `INSERT ... SELECT WHERE mutual`.
        # Returns the real id only when THIS like completed the pair (None otherwise),
        # so the client shows the overlay AND navigates to a thread that exists.
        match_id = await form_match_if_mutual(transaction, actor_id, recipient_id)
        if match_id is not None:
            # Side effect only — the row already exists; the task just pushes both sides.
            await dispatch_task(
                transaction,
                deps.request,
                TaskName.NOTIFY_MATCH,
                user_a_id=int(actor_id),
                user_b_id=int(recipient_id),
            )
        return ActionExecutionResponse(
            message="It's a match!" if match_id is not None else "Liked",
            invalidate_queries=[
                "/decisions",
                "/winger-tabs",
                "/matches",
                "/conversations",
                "/dating-profiles/me",
            ],
            # The real match id (non-null => client shows the overlay and opens the thread).
            created_id=match_id,
        )


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (pass) ─────────


@dating_profile_swipe_actions
class Pass(BaseObjectAction[DatingProfile, EmptyActionData]):
    """A dater passes on the target dating profile (upsert declined)."""

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.PASS
    label = "Pass"
    icon = ActionIcon.X

    @classmethod
    def is_available(cls, obj: DatingProfile, user: User, deps: ActionDeps) -> bool:
        return user.role is Role.DATER and obj.user_id != user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await apply_dater_decision(transaction, deps.state_machine_service, user, obj.user_id, DecisionState.DECLINED)
        return ActionExecutionResponse(
            message="Passed",
            invalidate_queries=["/decisions", "/winger-tabs", "/dating-profiles/me"],
        )


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (suggest) ──────


def _winger_targeting_other(obj: DatingProfile, user: User) -> bool:
    """A winger acting on a profile that isn't their own — the gate both winger
    swipe gestures (Suggest / DeclineForDater) share."""
    return user.role is Role.WINGER and obj.user_id != user.id


# Both winger gestures write a decision row on the dater's behalf via
# `insert_wing_suggestion`; the active-wingperson relationship is authorized by the
# `decisions` INSERT RLS policy's `WITH CHECK` (a non-active winger's insert is
# rejected at the policy layer and surfaced as a 403 by the dispatcher), so neither
# needs a redundant handler-side wingperson check.


@dating_profile_swipe_actions
class Suggest(BaseObjectAction[DatingProfile, SuggestActionData]):
    """A winger proposes the target dating profile to one of their daters.

    Creates a *pending* suggestion (decision NULL) that surfaces in the dater's
    pending-suggestions feed and pushes them — they must act on it (approve/pass).
    """

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.SUGGEST
    label = "Suggest"
    icon = ActionIcon.SEND

    @classmethod
    def is_available(cls, obj: DatingProfile, user: User, deps: ActionDeps) -> bool:
        return _winger_targeting_other(obj, user)

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: SuggestActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        winger_id = user.id
        recipient_id = obj.user_id
        if data.daterId == recipient_id:
            raise CannotSuggestSelfError()

        inserted = await insert_wing_suggestion(
            transaction,
            data.daterId,
            recipient_id,
            winger_id,
            data.note,
            DecisionState.PENDING,
        )

        # Notify only on a genuinely new suggestion — a no-op conflict (the pair was
        # already decided / already suggested) must not re-push the dater.
        if inserted:
            dater_token, winger_name = await dater_push_and_winger_name(transaction, data.daterId, winger_id)
            if dater_token is not None:
                await deps.push.send(
                    dater_token,
                    SUGGESTION_PUSH_TITLE,
                    f"{winger_name or 'Your wingperson'} suggested a profile for you to check out.",
                )

        return ActionExecutionResponse(
            message="Suggestion created",
            invalidate_queries=["/decisions", "/winger-tabs"],
        )


# ── POST /actions/dating_profile_swipe_actions/{datingProfileId} (decline) ──────


@dating_profile_swipe_actions
class DeclineForDater(BaseObjectAction[DatingProfile, DeclineForDaterData]):
    """A winger passes on the target dating profile on the dater's behalf.

    Records a `declined` decision so the profile leaves the dater's pool. Terminal —
    the dater is never notified (nothing for them to act on).
    """

    action_key: ClassVar[DatingProfileActionKey] = DatingProfileActionKey.DECLINE
    label = "Decline"
    icon = ActionIcon.X

    @classmethod
    def is_available(cls, obj: DatingProfile, user: User, deps: ActionDeps) -> bool:
        return _winger_targeting_other(obj, user)

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: DeclineForDaterData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        winger_id = user.id
        recipient_id = obj.user_id
        if data.daterId == recipient_id:
            raise CannotSuggestSelfError()

        await insert_wing_suggestion(
            transaction,
            data.daterId,
            recipient_id,
            winger_id,
            None,
            DecisionState.DECLINED,
        )

        return ActionExecutionResponse(
            message="Declined",
            invalidate_queries=["/decisions", "/winger-tabs"],
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
    def is_available(cls, obj: DatingProfile, user: User, deps: ActionDeps) -> bool:
        # Any viewer may report; never your own profile.
        return obj.user_id != user.id

    @classmethod
    async def execute(
        cls,
        obj: DatingProfile,
        data: ReportActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        reporter_id = user.id
        reported_id = obj.user_id
        await insert_report(transaction, reporter_id, reported_id, data.reason)
        # Block: ensure a DECLINED decision exists so the reported profile leaves the
        # reporter's queue — create it, or transition any prior like/pending row.
        await apply_dater_decision(transaction, deps.state_machine_service, user, reported_id, DecisionState.DECLINED)
        return ActionExecutionResponse(
            message="Report filed",
            invalidate_queries=[
                "/reports",
                "/decisions",
                "/winger-tabs",
                "/dating-profiles/me",
            ],
        )
