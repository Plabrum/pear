from __future__ import annotations

from typing import Literal

from app.platform.actions.schemas import ActionableList
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── Templates ──────────────────────────────────────────────────────────────────


class PromptTemplate(BaseSchema):
    id: Sqid
    question: str


# ── Prompt responses (winger/match comments) ────────────────────────────────────


class PromptResponseAuthor(BaseSchema):
    id: Sqid
    chosenName: str | None
    avatarUrl: str | None


class PromptResponse(ActionableList):
    id: Sqid
    profilePromptId: Sqid
    message: str
    isApproved: bool
    userId: Sqid
    createdAt: str
    author: PromptResponseAuthor | None


# ── Authored responses (responses the caller added) ──────────────────────────────

AuthoredResponseStatus = Literal["accepted", "pending", "not_accepted"]


class AuthoredPromptResponse(BaseSchema):
    """A prompt response the caller wrote, with the dater + question + verdict."""

    id: Sqid
    daterId: Sqid
    daterName: str
    promptQuestion: str
    message: str
    status: AuthoredResponseStatus
    createdAt: str


# GET /prompt-responses/me returns a bare JSON array.
AuthoredPromptResponsesResponse = list[AuthoredPromptResponse]


# ── Profile prompts (a dater's chosen prompt + answer) ───────────────────────────


class ProfilePrompt(ActionableList):
    id: Sqid
    datingProfileId: Sqid
    answer: str
    createdAt: str
    template: PromptTemplate
    responses: list[PromptResponse]


# ── Inputs ───────────────────────────────────────────────────────────────────


class CreateProfilePromptData(BaseSchema):
    """POST /profile-prompts body."""

    promptTemplateId: Sqid
    answer: str


class CreatePromptResponseData(BaseSchema):
    """POST /prompt-responses body."""

    profilePromptId: Sqid
    message: str
