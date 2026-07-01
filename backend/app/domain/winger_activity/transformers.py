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
from app.platform.media.client import BaseMediaClient


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
        # Prefix the decision id with `suggestion:` for a stable feed key.
        id=f"suggestion:{row.id}",
        daterId=row.dater_id,
        daterName=row.dater_name or "",
        suggestedName=row.recipient_name or "",
        status=status,
        createdAt=_iso(row.created_at),
    )


async def transform_photo(row: PhotoRow, media: BaseMediaClient) -> PhotoActivityRow:
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
        # `storage_url` holds an S3 key; serve a presigned GET URL. This feed is the
        # caller's OWN winger-activity (RLS-scoped), so the gate holds.
        storageUrl=await media.presign_download(row.storage_url),
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
