from __future__ import annotations

from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── Templates ──────────────────────────────────────────────────────────────────


class PromptTemplate(BaseSchema):
    id: UUID
    question: str


# ── Prompt responses (winger/match comments) ────────────────────────────────────


class PromptResponseAuthor(BaseSchema):
    id: UUID
    chosenName: str | None
    avatarUrl: str | None


class PromptResponse(BaseSchema):
    id: UUID
    profilePromptId: UUID
    message: str
    isApproved: bool
    userId: UUID
    createdAt: str
    author: PromptResponseAuthor | None


# ── Profile prompts (a dater's chosen prompt + answer) ───────────────────────────


class ProfilePrompt(BaseSchema):
    id: UUID
    datingProfileId: UUID
    answer: str
    createdAt: str
    template: PromptTemplate
    responses: list[PromptResponse]


# ── Inputs ───────────────────────────────────────────────────────────────────


class CreateProfilePromptData(BaseSchema):
    """POST /profile-prompts body."""

    promptTemplateId: UUID
    answer: str


class CreatePromptResponseData(BaseSchema):
    """POST /prompt-responses body."""

    profilePromptId: UUID
    message: str
