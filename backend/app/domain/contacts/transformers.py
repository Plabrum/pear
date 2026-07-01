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
    WingingForTab,
    Wingperson,
)
from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender
from app.platform.media.client import BaseMediaClient


def _iso(value: datetime | None) -> str:
    return value.isoformat() if value is not None else ""


def _avatar_url(key: str | None, media: BaseMediaClient) -> str | None:
    """Avatar keys resolve to a public-read URL (no presign needed)."""
    return media.public_url(key) if key else None


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


@dataclass
class WingingForTabRow:
    """A dater the caller actively wings for — the minimal `{id, name}` tab projection."""

    id: UUID
    chosen_name: str | None
    created_at: datetime | None


# ── Row -> struct mappers ────────────────────────────────────────────────────


def row_to_wingperson(row: WingpersonRow, media: BaseMediaClient) -> Wingperson:
    return Wingperson(
        id=row.id,
        createdAt=_iso(row.created_at),
        winger=(
            WingerSummary(
                id=row.winger_id,
                chosenName=row.winger_chosen_name,
                gender=row.winger_gender,
                avatarUrl=_avatar_url(row.winger_avatar_url, media),
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


def row_to_winging_for(row: WingingForDaterRow, media: BaseMediaClient) -> WingingForRow:
    return WingingForRow(
        id=row.id,
        createdAt=_iso(row.created_at),
        dater=(
            WingingForDater(
                id=row.dater_id,
                chosenName=row.dater_chosen_name,
                avatarUrl=_avatar_url(row.dater_avatar_url, media),
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


def rows_to_winging_for_tabs(rows: list[WingingForTabRow]) -> list[WingingForTab]:
    """Collapse the active-edge rows to distinct daters, preserving first-seen order."""
    seen: set[str] = set()
    tabs: list[WingingForTab] = []
    for row in rows:
        key = str(row.id)
        if key in seen:
            continue
        seen.add(key)
        tabs.append(WingingForTab(id=row.id, name=row.chosen_name or ""))
    return tabs
