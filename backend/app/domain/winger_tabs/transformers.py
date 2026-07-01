"""snake_case query rows -> camelCase msgspec structs for the winger-tabs domain.

Ported from `supabase/functions/api/domains/winger-tabs/transformers.ts`. Collapses
the newest-first rows to *distinct* wingers, preserving first-seen (i.e. most
recent) order — exactly the Hono `Set`-based dedupe.
"""

from __future__ import annotations

from app.domain.winger_tabs.queries import WingerTabRow
from app.domain.winger_tabs.schemas import WingerTab


def rows_to_winger_tabs(rows: list[WingerTabRow]) -> list[WingerTab]:
    seen: set[str] = set()
    tabs: list[WingerTab] = []
    for row in rows:
        key = str(row.id)
        if key in seen:
            continue
        seen.add(key)
        tabs.append(WingerTab(id=row.id, name=row.chosen_name or ""))
    return tabs
