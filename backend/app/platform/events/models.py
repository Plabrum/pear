from __future__ import annotations

from typing import Any

from sqlalchemy import Index, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.events.enums import EventType
from app.utils.sqids import Sqid, SqidType
from app.utils.textenum import TextEnum


class Event(BaseDBModel):
    """Append-only event log for object lifecycle tracking.

    Records structured events (create, update, state change, custom) with
    associated data. Read by the activity feed; written by `emit_event`.
    """

    __tablename__ = "events"

    actor_id: Mapped[Sqid | None] = mapped_column(SqidType, nullable=True, index=True)

    object_type: Mapped[str] = mapped_column(String(50), nullable=False)
    object_id: Mapped[Sqid] = mapped_column(SqidType, nullable=False)

    event_type: Mapped[EventType] = mapped_column(TextEnum(EventType), nullable=False)

    event_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (Index("ix_events_object", "object_type", "object_id", "created_at"),)

    def __repr__(self) -> str:
        return f"<Event({self.event_type.value}: {self.object_type}#{self.object_id} by actor {self.actor_id})>"
