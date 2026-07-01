"""Mutations for the reports domain — all writes live here as registered actions.

Ported from the POST handler in
`supabase/functions/api/domains/reports/route.ts`:

  * `FileReport` (POST /reports) -> BaseTopLevelAction

This is a TOP-LEVEL action: it keys off the (reporter, recipient) pair, not a
single `object_id`, so there is no row to load up front (the Hono handler inserted
a fresh report + upserted a decision by composite). `execute` runs both writes
under the request's RLS-scoped transaction; the action machinery commits on return
and rolls back on raise. The self-report guard is raised as a typed
`ApplicationError` (400), reproducing the Hono `HTTPException` — never an ad-hoc
response.

No state machine: filing a report inserts a `profile_reports` row and upserts a
`decision = 'declined'`. Neither the report nor the decision is a status move on an
existing row the platform `StateMachine` requires — both are INSERT/upsert
side-effects, mirroring how the decisions domain models its own writes. The decline
is what removes the reported profile from the reporter's queue, exactly as the Hono
handler did inline.

Registration: imported at boot by `discover_and_import([...], base_path="app/domain")`,
which runs `action_group_factory(...)` to register the group and decorates the action
class into the singleton `ActionRegistry`. The `ActionGroupType.REPORT_ACTIONS`
member is added to `app.platform.actions.enums` by the Integrate stage.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.reports.exceptions import CannotReportSelfError
from app.domain.reports.models import ProfileReport
from app.domain.reports.queries import insert_report, upsert_decline_decision
from app.domain.reports.schemas import CreateReportData
from app.platform.actions.base import BaseTopLevelAction, action_group_factory
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse

# ── Action group ───────────────────────────────────────────────────────────────

report_actions = action_group_factory(
    ActionGroupType.REPORT_ACTIONS,
    default_invalidation="reports",
    model_type=ProfileReport,
)


# ── POST /reports ────────────────────────────────────────────────────────────────


@report_actions
class FileReport(BaseTopLevelAction[CreateReportData]):
    """File a report against another user's profile.

    Two effects, matching the Hono handler:
      1. insert the `profile_reports` row, and
      2. upsert a `decision = 'declined'` for (reporter, recipient) so the reported
         profile leaves the reporter's swipe queue.
    """

    action_key = "file"  # type: ignore[assignment]
    label = "Report Profile"
    icon = ActionIcon.BLOCK

    @classmethod
    async def execute(
        cls,
        data: CreateReportData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        reporter_id = deps.user.id
        if reporter_id == data.recipientId:
            raise CannotReportSelfError()

        await insert_report(transaction, reporter_id, data.recipientId, data.reason)
        await upsert_decline_decision(transaction, reporter_id, data.recipientId)

        return ActionExecutionResponse(
            message="Report filed",
            # Filing a report declines the recipient, so the swipe feed (discover)
            # and the reporter's decisions both change.
            invalidate_queries=["reports", "decisions", "discover"],
        )
