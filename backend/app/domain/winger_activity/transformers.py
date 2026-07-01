"""snake_case query rows -> camelCase msgspec structs for the winger-activity domain.

Ported from `supabase/functions/api/domains/winger-activity/transformers.ts`. The
three `status` fields are folded here from the underlying decision/approval columns,
exactly as the Hono transformers do:

  * people : declined -> not_accepted; approved & has_match -> matched; else pending
  * photos : rejected_at -> not_accepted; approved_at -> approved; else pending
  * prompts: is_rejected -> not_accepted; is_approved -> accepted; else pending

Datetime columns render as ISO-8601 strings to match the Postgres
`timestamptz`->JSON contract the mobile app already consumes.
"""

from __future__ import annotations

from datetime import datetime

from app.domain.decisions.enums import DecisionType
from app.domain.winger_activity.queries import PhotoRow, PromptRow, SuggestionRow
from app.domain.winger_activity.schemas import (
    PeopleActivityRow,
    PeopleActivityStatus,
    PhotoActivityRow,
    PhotoActivityStatus,
    PromptActivityRow,
    PromptActivityStatus,
)


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def transform_suggestion(row: SuggestionRow) -> PeopleActivityRow:
    status: PeopleActivityStatus
    if row.decision is DecisionType.DECLINED:
        status = "not_accepted"
    elif row.decision is DecisionType.APPROVED and row.has_match:
        status = "matched"
    else:
        status = "pending"
    return PeopleActivityRow(
        # Hono prefixes the decision id with `suggestion:` for a stable feed key.
        id=f"suggestion:{row.id}",
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        suggestedName=row.recipient_name or "",
        status=status,
        createdAt=_iso(row.created_at),
    )


def transform_photo(row: PhotoRow) -> PhotoActivityRow:
    status: PhotoActivityStatus
    if row.rejected_at is not None:
        status = "not_accepted"
    elif row.approved_at is not None:
        status = "approved"
    else:
        status = "pending"
    return PhotoActivityRow(
        id=row.id,
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        storageUrl=row.storage_url,
        status=status,
        createdAt=_iso(row.created_at),
    )


def transform_prompt(row: PromptRow) -> PromptActivityRow:
    status: PromptActivityStatus
    if row.is_rejected:
        status = "not_accepted"
    elif row.is_approved:
        status = "accepted"
    else:
        status = "pending"
    return PromptActivityRow(
        id=row.id,
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        promptQuestion=row.prompt_question,
        message=row.message,
        status=status,
        createdAt=_iso(row.created_at),
    )
