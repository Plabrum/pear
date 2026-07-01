from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.actions.base import (
    BaseObjectAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from tests.fixtures.sample_domain.models import SampleStatus, SampleWidget
from tests.fixtures.sample_domain.state_machine import sample_machine

sample_widget_actions = action_group_factory(
    ActionGroupType.SAMPLE_WIDGET_ACTIONS,
    default_invalidation="sample_widgets",
    model_type=SampleWidget,
)


@sample_widget_actions
class ActivateWidget(BaseObjectAction[SampleWidget, EmptyActionData]):
    action_key = "activate"  # type: ignore[assignment]
    label = "Activate"
    icon = ActionIcon.CHECK
    target_state = SampleStatus.ACTIVE

    @classmethod
    def is_available(cls, obj: SampleWidget, deps: ActionDeps) -> bool:
        # Only a draft widget can be activated — proves state gating.
        return obj.state == SampleStatus.DRAFT

    @classmethod
    async def execute(
        cls,
        obj: SampleWidget,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await deps.state_machine_service.transition(
            sample_machine,
            obj,
            SampleStatus.ACTIVE,
            actor=deps.user,
        )
        return ActionExecutionResponse(
            message="Widget activated",
            invalidate_queries=["sample_widgets"],
        )
