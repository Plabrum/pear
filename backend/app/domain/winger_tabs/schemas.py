"""msgspec schemas for the winger-tabs domain.

Ported from `supabase/functions/api/domains/winger-tabs/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hook
consumes these.

Output struct (read-only — the winger-tabs domain has no mutations):
  * `WingerTab` — a distinct winger who has a pending suggestion for the viewer.
"""

from __future__ import annotations

from uuid import UUID

from app.platform.base.schemas import BaseSchema


class WingerTab(BaseSchema):
    id: UUID
    name: str


WingerTabsResponse = list[WingerTab]
