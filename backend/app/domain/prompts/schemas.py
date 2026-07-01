"""msgspec schemas for the prompts domain.

Ported from `supabase/functions/api/domains/prompts/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval
hooks consume these. Datetime columns render as ISO-8601 strings (the
timestamptz -> JSON contract the app already consumes).

Output structs:
  * `PromptTemplate`        -> GET /prompt-templates(/onboarding)
  * `ProfilePrompt`         -> GET /profile-prompts/me (+ create response)
  * `PromptResponse`        -> create / approve a response

Input structs (consumed by the actions layer):
  * `CreateProfilePromptData`  -> POST /profile-prompts
  * `CreatePromptResponseData` -> POST /prompt-responses
"""

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
