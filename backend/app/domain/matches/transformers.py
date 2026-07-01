from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.dating_profiles.enums import City, Interest
from app.domain.matches.models import Match
from app.domain.matches.schemas import (
    MatchSheet,
    MatchSheetPrompt,
    MatchSheetPromptTemplate,
    MatchSheetWinger,
    MatchSheetWingNote,
    MatchSummary,
    MatchSummaryOther,
)
from app.platform.actions.hydrate import actions_for
from app.platform.media.client import BaseMediaClient
from app.utils.sqids import Sqid

if TYPE_CHECKING:
    # Type-only: importing `ActionGroup`/`ActionDeps` at runtime would close an
    # import cycle (transformers → actions.base → actions.deps → realtime.service →
    # realtime.channels → messages.queries → ... ). `from __future__ import
    # annotations` keeps the parameter annotations as strings, so the runtime path
    # never needs these symbols — `actions_for` is the only runtime dependency and
    # it carries no such back-edge into matches.
    from app.platform.actions.base import ActionGroup
    from app.platform.actions.deps import ActionDeps


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


@dataclass
class MatchRow:
    """One row of the matches list aggregate."""

    match_id: Sqid
    created_at: datetime | None
    has_messages: bool
    other_user_id: Sqid
    # The match's two participant ids (ordered: user_a_id < user_b_id). Carried so a
    # transient `Match` stub can feed the MESSAGE_ACTIONS gate (`_viewer_in_match`),
    # which reads ONLY these two scalar columns.
    user_a_id: Sqid
    user_b_id: Sqid
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
    suggested_by: Sqid | None
    winger_id: Sqid | None
    winger_chosen_name: str | None


@dataclass
class MatchPromptRow:
    id: Sqid
    answer: str
    template_id: Sqid | None
    template_question: str | None


async def row_to_match(row: MatchRow, media: BaseMediaClient, group: ActionGroup, deps: ActionDeps) -> MatchSummary:
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
    summary = MatchSummary(
        matchId=row.match_id,
        createdAt=_iso(row.created_at),
        hasMessages=row.has_messages,
        other=other,
    )
    # The MESSAGE_ACTIONS gate (`_viewer_in_match`) reads ONLY Match.user_a_id /
    # user_b_id — never a relationship — so a transient stub carrying just those
    # scalar identity columns is sufficient (and adds zero DB round-trips). Do NOT
    # add it to the session.
    stub = Match(id=row.match_id, user_a_id=row.user_a_id, user_b_id=row.user_b_id)
    summary.actions = actions_for(group, deps, stub)
    return summary


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
