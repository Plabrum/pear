"""Query rows -> camelCase msgspec structs for the contacts domain.

Ported from `supabase/functions/api/domains/contacts/transformers.ts`. The Hono
transformers map Drizzle rows (snake_case) onto the Zod response shapes (camelCase);
here we map plain row dataclasses (assembled in `queries.py`) onto the msgspec
structs. `created_at` (a Postgres `timestamptz`) is rendered as an ISO-8601 string
to match the JSON contract the mobile app already consumes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.contacts.schemas import (
    DaterSummary,
    IncomingInvitation,
    SentInvitation,
    WingerSummary,
    WingingForDater,
    WingingForRow,
    Wingperson,
)
from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


# ── Row shapes (the loose tuples `queries.py` assembles) ─────────────────────


@dataclass
class WingpersonRow:
    id: UUID
    created_at: datetime
    winger_id: UUID | None
    winger_chosen_name: str | None
    winger_gender: Gender | None
    winger_avatar_url: str | None


@dataclass
class IncomingInvitationRow:
    id: UUID
    created_at: datetime
    dater_id: UUID | None
    dater_chosen_name: str | None


@dataclass
class WingingForDaterRow:
    id: UUID
    created_at: datetime
    dater_id: UUID | None
    dater_chosen_name: str | None
    dater_avatar_url: str | None
    dater_interests: list[Interest] | None
    dater_bio: str | None


@dataclass
class SentInvitationRow:
    id: UUID
    created_at: datetime
    phone_number: str
    winger_id: UUID | None
    winger_chosen_name: str | None


# ── Row -> struct mappers ────────────────────────────────────────────────────


def row_to_wingperson(row: WingpersonRow) -> Wingperson:
    return Wingperson(
        id=row.id,
        createdAt=_iso(row.created_at),
        winger=(
            WingerSummary(
                id=row.winger_id,
                chosenName=row.winger_chosen_name,
                gender=row.winger_gender,
                avatarUrl=row.winger_avatar_url,
            )
            if row.winger_id is not None
            else None
        ),
    )


def row_to_incoming_invitation(row: IncomingInvitationRow) -> IncomingInvitation:
    return IncomingInvitation(
        id=row.id,
        createdAt=_iso(row.created_at),
        dater=(DaterSummary(id=row.dater_id, chosenName=row.dater_chosen_name) if row.dater_id is not None else None),
    )


def row_to_winging_for(row: WingingForDaterRow) -> WingingForRow:
    return WingingForRow(
        id=row.id,
        createdAt=_iso(row.created_at),
        dater=(
            WingingForDater(
                id=row.dater_id,
                chosenName=row.dater_chosen_name,
                avatarUrl=row.dater_avatar_url,
                interests=row.dater_interests,
                bio=row.dater_bio,
            )
            if row.dater_id is not None
            else None
        ),
    )


def row_to_sent_invitation(row: SentInvitationRow) -> SentInvitation:
    return SentInvitation(
        id=row.id,
        createdAt=_iso(row.created_at),
        phoneNumber=row.phone_number,
        winger=(
            DaterSummary(id=row.winger_id, chosenName=row.winger_chosen_name) if row.winger_id is not None else None
        ),
    )
