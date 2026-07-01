from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── computed status literals ─────────────────────────────────────────────────

PeopleActivityStatus = Literal["matched", "pending", "not_accepted"]
PhotoActivityStatus = Literal["approved", "pending", "not_accepted"]
PromptActivityStatus = Literal["accepted", "pending", "not_accepted"]


# ── GET /winger-activity/people ──────────────────────────────────────────────


class PeopleActivityRow(BaseSchema):
    # The decision id is prefixed with `suggestion:` (see transformers), so this is
    # a plain string, not a UUID.
    id: str
    daterId: UUID
    daterName: str
    suggestedName: str
    status: PeopleActivityStatus
    createdAt: str


# ── GET /winger-activity/photos ──────────────────────────────────────────────


class PhotoActivityRow(BaseSchema):
    id: UUID
    daterId: UUID
    daterName: str
    storageUrl: str
    status: PhotoActivityStatus
    createdAt: str


# ── GET /winger-activity/prompts ─────────────────────────────────────────────


class PromptActivityRow(BaseSchema):
    id: UUID
    daterId: UUID
    daterName: str
    promptQuestion: str
    message: str
    status: PromptActivityStatus
    createdAt: str


WingerPeopleActivityResponse = list[PeopleActivityRow]
WingerPhotosActivityResponse = list[PhotoActivityRow]
WingerPromptsActivityResponse = list[PromptActivityRow]
