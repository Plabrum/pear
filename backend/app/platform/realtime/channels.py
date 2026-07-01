from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.messages.queries import is_viewer_in_match

# ── Channel name builders (mirror the client strings) ──────────────────────────

MESSAGES_LIST_CHANNEL = "presence:messages-list"


def match_channel(match_id: UUID | str) -> str:
    return f"messages:match:{match_id}"


def _sorted_pair(a: UUID | str, b: UUID | str) -> str:
    return ":".join(sorted([str(a), str(b)]))


def presence_pair_channel(a: UUID | str, b: UUID | str) -> str:
    return f"presence:{_sorted_pair(a, b)}"


def typing_pair_channel(a: UUID | str, b: UUID | str) -> str:
    return f"typing:{_sorted_pair(a, b)}"


# ── Parsed channel kinds ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class MatchChannel:
    match_id: UUID


@dataclass(frozen=True)
class PresencePairChannel:
    a: UUID
    b: UUID


@dataclass(frozen=True)
class TypingPairChannel:
    a: UUID
    b: UUID


@dataclass(frozen=True)
class MessagesListChannel:
    pass


ParsedChannel = MatchChannel | PresencePairChannel | TypingPairChannel | MessagesListChannel


def _parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except (ValueError, AttributeError):
        return None


def parse_channel(name: str) -> ParsedChannel | None:
    """Parse a client channel string into a typed kind, or None if unrecognized."""
    if name == MESSAGES_LIST_CHANNEL:
        return MessagesListChannel()

    if name.startswith("messages:match:"):
        match_id = _parse_uuid(name.removeprefix("messages:match:"))
        return MatchChannel(match_id=match_id) if match_id is not None else None

    if name.startswith("presence:"):
        rest = name.removeprefix("presence:")
        parts = rest.split(":")
        if len(parts) != 2:
            return None
        a, b = _parse_uuid(parts[0]), _parse_uuid(parts[1])
        return PresencePairChannel(a=a, b=b) if a is not None and b is not None else None

    if name.startswith("typing:"):
        rest = name.removeprefix("typing:")
        parts = rest.split(":")
        if len(parts) != 2:
            return None
        a, b = _parse_uuid(parts[0]), _parse_uuid(parts[1])
        return TypingPairChannel(a=a, b=b) if a is not None and b is not None else None

    return None


async def authorize_channel(db: AsyncSession, user_id: UUID, channel: str) -> bool:
    """RLS-equivalent subscribe gate: may `user_id` join `channel`?

    `db` is an RLS-scoped session set to `user_id` (so the match-participant check is
    itself RLS-enforced — the `is_viewer_in_match` SELECT only sees matches the
    viewer is party to). An unrecognized channel is denied.
    """
    parsed = parse_channel(channel)
    match parsed:
        case MessagesListChannel():
            return True
        case MatchChannel(match_id=match_id):
            return await is_viewer_in_match(db, user_id, match_id)
        case PresencePairChannel(a=a, b=b):
            return user_id in (a, b)
        case TypingPairChannel(a=a, b=b):
            return user_id in (a, b)
        case _:
            return False
