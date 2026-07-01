"""msgspec schemas for the reports domain.

Ported from `supabase/functions/api/domains/reports/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hooks
consume these.

The Hono domain is write-only (a single `POST /reports`); there are no read
endpoints, so there is no `ReportListItem` / `ReportDetail`. The action's input is
`CreateReportData` (the Zod `ReportRequest`), and the documented success body is
`ReportResponse` (`{ ok: true }`). In the Litestar port the write is exposed
through the generic actions router, whose `ActionExecutionResponse` carries the
result; `ReportResponse` is retained as the shape the Orval step reconciles against
the legacy `{ ok: true }` contract.
"""

from __future__ import annotations

from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── Action input shape ───────────────────────────────────────────────────────


class CreateReportData(BaseSchema):
    """POST /reports body — file a report against another user's profile.

    Mirrors the Zod `ReportRequest`: `recipientId` is a UUID and `reason` is a
    non-empty string (Hono enforced 1..500 chars).
    """

    recipientId: UUID
    reason: str


# ── Documented success body (legacy `{ ok: true }`) ──────────────────────────


class ReportResponse(BaseSchema):
    """POST /reports success body — preserved for the Orval/OpenAPI reconciliation."""

    ok: bool
