from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.dating_profiles.enums import City, Interest
from app.domain.matches.schemas import (
    MatchSheet,
    MatchSheetPrompt,
    MatchSheetPromptTemplate,
    MatchSheetWinger,
    MatchSheetWingNote,
    MatchSummary,
    MatchSummaryOther,
)
from app.platform.media.client import BaseMediaClient


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


@dataclass
class MatchRow:
    """One row of the matches list aggregate."""

    match_id: UUID
    created_at: datetime | None
    has_messages: bool
    other_user_id: UUID
    chosen_name: str | None
    date_of_birth: datetime | None
    age: int | None
    city: City | None
    bio: str | None
    interests: list[Interest] | None
    first_photo: str | None  # S3 key (approved only) — presigned at transform time


@dataclass
class WingNoteRow:
    note: str | None
    suggested_by: UUID | None
    winger_id: UUID | None
    winger_chosen_name: str | None


@dataclass
class MatchPromptRow:
    id: UUID
    answer: str
    template_id: UUID | None
    template_question: str | None


async def row_to_match(row: MatchRow, media: BaseMediaClient) -> MatchSummary:
    # `first_photo` is the other user's first APPROVED photo key (the query filters
    # approved_at IS NOT NULL), so presigning it is safe. None stays None.
    first_photo = await media.presign_download(row.first_photo) if row.first_photo is not None else None
    other = MatchSummaryOther(
        id=row.other_user_id,
        chosenName=row.chosen_name,
        dateOfBirth=_iso(row.date_of_birth) if row.date_of_birth is not None else None,
        age=row.age,
        city=row.city,
        bio=row.bio,
        interests=list(row.interests) if row.interests is not None else [],
        firstPhoto=first_photo,
    )
    return MatchSummary(
        matchId=row.match_id,
        createdAt=_iso(row.created_at),
        hasMessages=row.has_messages,
        other=other,
    )


def row_to_wing_note(row: WingNoteRow | None) -> MatchSheetWingNote | None:
    if row is None or row.note is None:
        return None
    return MatchSheetWingNote(
        note=row.note,
        suggestedBy=row.suggested_by,
        winger=(
            MatchSheetWinger(id=row.winger_id, chosenName=row.winger_chosen_name) if row.winger_id is not None else None
        ),
    )


def row_to_match_prompt(row: MatchPromptRow) -> MatchSheetPrompt:
    return MatchSheetPrompt(
        id=row.id,
        answer=row.answer,
        template=(
            MatchSheetPromptTemplate(id=row.template_id, question=row.template_question or "")
            if row.template_id is not None
            else None
        ),
    )


def build_match_sheet(
    wing_note_row: WingNoteRow | None,
    prompt_rows: list[MatchPromptRow],
) -> MatchSheet:
    return MatchSheet(
        wingNote=row_to_wing_note(wing_note_row),
        prompts=[row_to_match_prompt(r) for r in prompt_rows],
    )
