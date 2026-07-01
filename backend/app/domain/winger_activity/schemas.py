"""msgspec schemas for the winger-activity domain.

Ported from `supabase/functions/api/domains/winger-activity/schemas.ts`. Field
names are camelCase to match the Hono Zod output byte-for-byte — the mobile app's
Orval hooks consume these.

The three `status` fields are *computed* on the server (folded from
decision/has_match, approved_at/rejected_at, is_approved/is_rejected) rather than
read from a stored column, so they are typed as `Literal` unions matching the Zod
`z.enum([...])` wire form — there is no stored `TextEnum` to derive them from.

Output structs (all read-only — the winger-activity domain has no mutations):
  * `PeopleActivityRow` (status: matched | pending | not_accepted)
  * `PhotoActivityRow`  (status: approved | pending | not_accepted)
  * `PromptActivityRow` (status: accepted | pending | not_accepted)
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── computed status literals (Zod z.enum mirrors) ────────────────────────────

PeopleActivityStatus = Literal["matched", "pending", "not_accepted"]
PhotoActivityStatus = Literal["approved", "pending", "not_accepted"]
PromptActivityStatus = Literal["accepted", "pending", "not_accepted"]


# ── GET /winger-activity/people ──────────────────────────────────────────────


class PeopleActivityRow(BaseSchema):
    # Hono prefixes the decision id with `suggestion:` (see transformers), so this
    # is a plain string, not a UUID.
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
