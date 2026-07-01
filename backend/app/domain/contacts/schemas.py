"""msgspec schemas for the contacts (wingperson roster) domain.

Ported from `supabase/functions/api/domains/contacts/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hooks
consume these. Enum-typed fields use the domain `Enum` classes directly; msgspec
serializes an Enum by its `.value`, which is exactly the wire format the Zod enums
emit (`'Male'`, `'Travel'`, …).

Output shapes (the combined GET /wingpeople bundle): `Wingperson` /
`IncomingInvitation` / `WingingForRow` / `SentInvitation` + `WingpeopleResponse`,
plus the invite mutation's `InviteWingpersonResponse`. Input shape (consumed by the
actions layer): `InviteWingpersonData` ({phoneNumber}).

Unlike the profiles domain there is no PATCH-style optional input here — invite/
accept/decline/remove either take a single required field or no body at all — so
`UNSET` is not needed.
"""

from __future__ import annotations

from uuid import UUID

from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender
from app.platform.base.schemas import BaseSchema

# ── Nested summaries ─────────────────────────────────────────────────────────


class WingerSummary(BaseSchema):
    id: UUID
    chosenName: str | None
    gender: Gender | None
    avatarUrl: str | None


class DaterSummary(BaseSchema):
    id: UUID
    chosenName: str | None


class WingingForDater(BaseSchema):
    id: UUID
    chosenName: str | None
    avatarUrl: str | None
    interests: list[Interest] | None
    bio: str | None


# ── Roster rows ──────────────────────────────────────────────────────────────


class Wingperson(BaseSchema):
    id: UUID
    createdAt: str
    winger: WingerSummary | None


class IncomingInvitation(BaseSchema):
    id: UUID
    createdAt: str
    dater: DaterSummary | None


class WingingForRow(BaseSchema):
    id: UUID
    createdAt: str
    dater: WingingForDater | None


class SentInvitation(BaseSchema):
    id: UUID
    createdAt: str
    phoneNumber: str
    winger: DaterSummary | None


# ── Combined GET /wingpeople response ────────────────────────────────────────


class WingpeopleResponse(BaseSchema):
    wingpeople: list[Wingperson]
    invitations: list[IncomingInvitation]
    wingingFor: list[WingingForRow]
    sentInvitations: list[SentInvitation]
    # contactId -> count of suggestions in the last 7 days (Zod: z.record(uuid, int)).
    weeklyCounts: dict[str, int]


# ── Invite mutation (POST /wingpeople/invite) ────────────────────────────────


class InviteWingpersonData(BaseSchema):
    """POST /wingpeople/invite body."""

    phoneNumber: str


class InviteWingpersonResponse(BaseSchema):
    id: UUID
    phoneNumber: str
    wingerId: UUID | None
