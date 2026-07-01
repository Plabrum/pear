from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.exceptions import (
    DatingProfileNotFoundError,
    NotWingpersonOrMatchError,
    ProfilePromptNotFoundError,
)
from app.domain.prompts.models import ProfilePrompt, PromptResponse
from app.domain.prompts.queries import (
    fetch_own_dating_profile_id,
    fetch_profile_prompt_owner,
    is_active_wingperson,
    is_matched_with,
    is_response_profile_owner,
)
from app.domain.prompts.schemas import (
    CreateProfilePromptData,
    CreatePromptResponseData,
)
from app.domain.prompts.state_machine import adapt, prompt_response_approval_machine
from app.platform.actions.base import (
    BaseObjectAction,
    BaseTopLevelAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from app.platform.state_machine.roles import Role

# ── Action groups ───────────────────────────────────────────────────────────────

profile_prompt_actions = action_group_factory(
    ActionGroupType.PROFILE_PROMPT_ACTIONS,
    default_invalidation="profile_prompts",
    model_type=ProfilePrompt,
)

prompt_response_actions = action_group_factory(
    ActionGroupType.PROMPT_RESPONSE_ACTIONS,
    default_invalidation="prompt_responses",
    model_type=PromptResponse,
)


# ── POST /profile-prompts ───────────────────────────────────────────────────────


@profile_prompt_actions
class CreateProfilePrompt(BaseTopLevelAction[CreateProfilePromptData]):
    action_key = "create"
    label = "Add Prompt"
    icon = ActionIcon.ADD

    @classmethod
    async def execute(
        cls,
        data: CreateProfilePromptData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        dating_profile_id = await fetch_own_dating_profile_id(transaction, deps.user.id)
        if dating_profile_id is None:
            raise DatingProfileNotFoundError()

        prompt = ProfilePrompt(
            dating_profile_id=dating_profile_id,
            prompt_template_id=data.promptTemplateId,
            answer=data.answer,
        )
        transaction.add(prompt)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Prompt added",
            invalidate_queries=["profile_prompts", "dating_profiles"],
            created_id=prompt.id,
        )


# ── DELETE /profile-prompts/{id} ────────────────────────────────────────────────


@profile_prompt_actions
class DeleteProfilePrompt(BaseObjectAction[ProfilePrompt, EmptyActionData]):
    action_key = "delete"
    label = "Delete Prompt"
    icon = ActionIcon.TRASH

    @classmethod
    def is_available(cls, obj: ProfilePrompt, deps: ActionDeps) -> bool:
        # Only a dater may delete a prompt; the precise owner predicate (does this
        # dater own the prompt's dating profile) is verified in execute via a join.
        return deps.user.role is Role.DATER

    @classmethod
    async def execute(
        cls,
        obj: ProfilePrompt,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await fetch_profile_prompt_owner(transaction, obj.id)
        if owner_id != deps.user.id:
            # "Profile prompt not found for this caller" (404).
            raise ProfilePromptNotFoundError()

        # Soft delete (the codebase hides `deleted_at IS NOT NULL` from every SELECT)
        # — the observable contract (the row disappears) is preserved.
        obj.soft_delete()
        await transaction.flush()
        return ActionExecutionResponse(
            message="Prompt deleted",
            invalidate_queries=["profile_prompts", "dating_profiles"],
        )


# ── POST /prompt-responses ──────────────────────────────────────────────────────


@prompt_response_actions
class CreatePromptResponse(BaseTopLevelAction[CreatePromptResponseData]):
    action_key = "create"
    label = "Add Comment"
    icon = ActionIcon.MESSAGE

    @classmethod
    async def execute(
        cls,
        data: CreatePromptResponseData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await fetch_profile_prompt_owner(transaction, data.profilePromptId)
        if owner_id is None:
            raise ProfilePromptNotFoundError()

        caller_id = deps.user.id
        if owner_id != caller_id:
            winger = await is_active_wingperson(transaction, owner_id, caller_id)
            matched = await is_matched_with(transaction, caller_id, owner_id)
            if not winger and not matched:
                raise NotWingpersonOrMatchError()

        response = PromptResponse(
            user_id=caller_id,
            profile_prompt_id=data.profilePromptId,
            message=data.message,
        )
        transaction.add(response)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Comment added",
            invalidate_queries=["prompt_responses", "profile_prompts"],
            created_id=response.id,
        )


# ── POST /prompt-responses/{id}/approve ─────────────────────────────────────────


@prompt_response_actions
class ApprovePromptResponse(BaseObjectAction[PromptResponse, EmptyActionData]):
    action_key = "approve"
    label = "Approve Comment"
    icon = ActionIcon.CHECK
    target_state = ApprovalState.APPROVED

    @classmethod
    def is_available(cls, obj: PromptResponse, deps: ActionDeps) -> bool:
        # Only a dater (the profile owner) may approve, and only while pending.
        # The exact owner predicate is verified in execute (async join).
        return deps.user.role is Role.DATER and not obj.is_approved and not obj.is_rejected

    @classmethod
    async def execute(
        cls,
        obj: PromptResponse,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        if not await is_response_profile_owner(transaction, obj, deps.user.id):
            # "Prompt response not found for this caller" (404).
            raise ProfilePromptNotFoundError()

        # Drive the approval through the state machine (logs + emits an event)
        # rather than assigning is_approved directly. The adapter projects the
        # booleans onto ApprovalState and writes them back on transition.
        await deps.state_machine_service.transition(
            prompt_response_approval_machine,
            adapt(obj),
            ApprovalState.APPROVED,
            actor=deps.user,
        )
        await transaction.flush()
        return ActionExecutionResponse(
            message="Comment approved",
            invalidate_queries=["prompt_responses", "profile_prompts"],
        )


# ── DELETE /prompt-responses/{id} ───────────────────────────────────────────────


@prompt_response_actions
class DeletePromptResponse(BaseObjectAction[PromptResponse, EmptyActionData]):
    action_key = "delete"
    label = "Delete Comment"
    icon = ActionIcon.TRASH

    @classmethod
    def is_available(cls, obj: PromptResponse, deps: ActionDeps) -> bool:
        # The author may always delete their own comment. A dater may delete a
        # comment on their own profile (the owner predicate is verified in execute).
        return obj.user_id == deps.user.id or deps.user.role is Role.DATER

    @classmethod
    async def execute(
        cls,
        obj: PromptResponse,
        data: EmptyActionData,
        transaction: AsyncSession,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        caller_id = deps.user.id
        is_author = obj.user_id == caller_id
        is_owner = is_author or await is_response_profile_owner(transaction, obj, caller_id)
        if not is_owner:
            # "Prompt response not found for this caller" (404).
            raise ProfilePromptNotFoundError()

        # Soft delete — the soft-delete SELECT filter hides the row afterward,
        # preserving the observable contract (the row disappears).
        obj.soft_delete()
        await transaction.flush()
        return ActionExecutionResponse(
            message="Comment deleted",
            invalidate_queries=["prompt_responses", "profile_prompts"],
        )
