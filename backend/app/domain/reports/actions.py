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

    Two effects:
      1. insert the `profile_reports` row, and
      2. upsert a `decision = 'declined'` for (reporter, recipient) so the reported
         profile leaves the reporter's swipe queue.
    """

    action_key = "file"
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
