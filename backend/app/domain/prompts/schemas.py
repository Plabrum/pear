from __future__ import annotations

from typing import Literal
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


# ── Authored responses (responses the caller added) ──────────────────────────────

AuthoredResponseStatus = Literal["accepted", "pending", "not_accepted"]


class AuthoredPromptResponse(BaseSchema):
    """A prompt response the caller wrote, with the dater + question + verdict."""

    id: UUID
    daterId: UUID
    daterName: str
    promptQuestion: str
    message: str
    status: AuthoredResponseStatus
    createdAt: str


# GET /prompt-responses/me returns a bare JSON array.
AuthoredPromptResponsesResponse = list[AuthoredPromptResponse]


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
