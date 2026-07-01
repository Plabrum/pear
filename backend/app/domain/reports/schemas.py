from __future__ import annotations

from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── Action input shape ───────────────────────────────────────────────────────


class CreateReportData(BaseSchema):
    """POST /reports body — file a report against another user's profile.

    `recipientId` is a UUID and `reason` is a non-empty string (1..500 chars).
    """

    recipientId: UUID
    reason: str


# ── Documented success body (`{ ok: true }`) ─────────────────────────────────


class ReportResponse(BaseSchema):
    """POST /reports success body — preserved for the Orval/OpenAPI reconciliation."""

    ok: bool
