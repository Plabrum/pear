from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

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
from app.platform.auth.principal import User
from app.platform.state_machine.roles import Role

# ── Action groups ───────────────────────────────────────────────────────────────


class ProfilePromptActionKey(StrEnum):
    CREATE = "create"
    DELETE = "delete"


class PromptResponseActionKey(StrEnum):
    CREATE = "create"
    APPROVE = "approve"
    DELETE = "delete"


profile_prompt_actions = action_group_factory(
    ActionGroupType.PROFILE_PROMPT_ACTIONS,
    default_invalidation="/profile-prompts",
    model_type=ProfilePrompt,
)

prompt_response_actions = action_group_factory(
    ActionGroupType.PROMPT_RESPONSE_ACTIONS,
    default_invalidation="/prompt-responses",
    model_type=PromptResponse,
)


# ── POST /profile-prompts ───────────────────────────────────────────────────────


@profile_prompt_actions
class CreateProfilePrompt(BaseTopLevelAction[CreateProfilePromptData]):
    action_key: ClassVar[ProfilePromptActionKey] = ProfilePromptActionKey.CREATE
    label = "Add Prompt"
    icon = ActionIcon.ADD

    @classmethod
    async def execute(
        cls,
        data: CreateProfilePromptData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        dating_profile_id = await fetch_own_dating_profile_id(transaction, user.id)
        if dating_profile_id is None:
            raise DatingProfileNotFoundError()

        prompt = ProfilePrompt(
            dating_profile_id=dating_profile_id,
            owner_id=user.id,
            prompt_template_id=data.promptTemplateId,
            answer=data.answer,
        )
        transaction.add(prompt)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Prompt added",
            invalidate_queries=["/profile-prompts", "/dating-profiles/me"],
            created_id=prompt.id,
        )


# ── DELETE /profile-prompts/{id} ────────────────────────────────────────────────


@profile_prompt_actions
class DeleteProfilePrompt(BaseObjectAction[ProfilePrompt, EmptyActionData]):
    action_key: ClassVar[ProfilePromptActionKey] = ProfilePromptActionKey.DELETE
    label = "Delete Prompt"
    icon = ActionIcon.TRASH

    @classmethod
    def is_available(cls, obj: ProfilePrompt, user: User, deps: ActionDeps) -> bool:
        # Only the owning dater may delete a prompt — flat column compare on owner_id.
        return user.role is Role.DATER and obj.owner_id == user.id

    @classmethod
    async def execute(
        cls,
        obj: ProfilePrompt,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        # Soft delete (the codebase hides `deleted_at IS NOT NULL` from every SELECT)
        # — the observable contract (the row disappears) is preserved.
        obj.soft_delete()
        await transaction.flush()
        return ActionExecutionResponse(
            message="Prompt deleted",
            invalidate_queries=["/profile-prompts", "/dating-profiles/me"],
        )


# ── POST /prompt-responses ──────────────────────────────────────────────────────


@prompt_response_actions
class CreatePromptResponse(BaseTopLevelAction[CreatePromptResponseData]):
    action_key: ClassVar[PromptResponseActionKey] = PromptResponseActionKey.CREATE
    label = "Add Comment"
    icon = ActionIcon.MESSAGE

    @classmethod
    async def execute(
        cls,
        data: CreatePromptResponseData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        owner_id = await fetch_profile_prompt_owner(transaction, data.profilePromptId)
        if owner_id is None:
            raise ProfilePromptNotFoundError()

        caller_id = user.id
        if owner_id != caller_id:
            winger = await is_active_wingperson(transaction, owner_id, caller_id)
            matched = await is_matched_with(transaction, caller_id, owner_id)
            if not winger and not matched:
                raise NotWingpersonOrMatchError()

        response = PromptResponse(
            user_id=caller_id,
            profile_owner_id=owner_id,
            profile_prompt_id=data.profilePromptId,
            message=data.message,
        )
        transaction.add(response)
        await transaction.flush()
        return ActionExecutionResponse(
            message="Comment added",
            invalidate_queries=["/prompt-responses", "/profile-prompts"],
            created_id=response.id,
        )


# ── POST /prompt-responses/{id}/approve ─────────────────────────────────────────


@prompt_response_actions
class ApprovePromptResponse(BaseObjectAction[PromptResponse, EmptyActionData]):
    action_key: ClassVar[PromptResponseActionKey] = PromptResponseActionKey.APPROVE
    label = "Approve Comment"
    icon = ActionIcon.CHECK
    target_state = ApprovalState.APPROVED

    @classmethod
    def is_available(cls, obj: PromptResponse, user: User, deps: ActionDeps) -> bool:
        # Only the profile-owning dater may approve, and only while pending —
        # ownership is a flat column compare on profile_owner_id.
        return (
            user.role is Role.DATER and not obj.is_approved and not obj.is_rejected and obj.profile_owner_id == user.id
        )

    @classmethod
    async def execute(
        cls,
        obj: PromptResponse,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        # Drive the approval through the state machine (logs + emits an event)
        # rather than assigning is_approved directly. The adapter projects the
        # booleans onto ApprovalState and writes them back on transition.
        await deps.state_machine_service.transition(
            prompt_response_approval_machine,
            adapt(obj),
            ApprovalState.APPROVED,
            actor=user,
        )
        await transaction.flush()
        return ActionExecutionResponse(
            message="Comment approved",
            invalidate_queries=["/prompt-responses", "/profile-prompts"],
        )


# ── DELETE /prompt-responses/{id} ───────────────────────────────────────────────


@prompt_response_actions
class DeletePromptResponse(BaseObjectAction[PromptResponse, EmptyActionData]):
    action_key: ClassVar[PromptResponseActionKey] = PromptResponseActionKey.DELETE
    label = "Delete Comment"
    icon = ActionIcon.TRASH

    @classmethod
    def is_available(cls, obj: PromptResponse, user: User, deps: ActionDeps) -> bool:
        # The author may delete their own comment; the profile owner may delete a
        # comment on their profile — both flat column compares on the row.
        return obj.user_id == user.id or obj.profile_owner_id == user.id

    @classmethod
    async def execute(
        cls,
        obj: PromptResponse,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        # Soft delete — the soft-delete SELECT filter hides the row afterward,
        # preserving the observable contract (the row disappears).
        obj.soft_delete()
        await transaction.flush()
        return ActionExecutionResponse(
            message="Comment deleted",
            invalidate_queries=["/prompt-responses", "/profile-prompts"],
        )
