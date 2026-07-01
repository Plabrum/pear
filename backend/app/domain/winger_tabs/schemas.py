from __future__ import annotations

from uuid import UUID

from app.platform.base.schemas import BaseSchema


class WingerTab(BaseSchema):
    id: UUID
    name: str


WingerTabsResponse = list[WingerTab]
