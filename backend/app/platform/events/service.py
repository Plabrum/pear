from __future__ import annotations

import logging
from dataclasses import asdict, is_dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.base.models import BaseDBModel
from app.platform.events.enums import EventType
from app.platform.events.models import Event
from app.platform.events.schemas import (
    CreatedEventData,
    CustomEventData,
    StateChangedEventData,
    UpdatedEventData,
)

logger = logging.getLogger(__name__)

EventDataTypes = CreatedEventData | UpdatedEventData | StateChangedEventData | CustomEventData | dict[str, Any] | None


async def emit_event(
    session: AsyncSession,
    event_type: EventType,
    obj: BaseDBModel,
    user_id: UUID | None,
    event_data: EventDataTypes = None,
) -> Event:
    """Persist an Event row in the caller's transaction and return it.

    `user_id` is the actor (None for SYSTEM-initiated events). `event_data` may be
    a typed dataclass payload (serialized via `asdict`) or a plain dict.
    """
    data_dict: dict[str, Any] | None
    if event_data is None:
        data_dict = None
    elif isinstance(event_data, dict):
        data_dict = event_data
    elif is_dataclass(event_data) and not isinstance(event_data, type):
        data_dict = asdict(event_data)
    else:
        raise TypeError(f"Unsupported event_data type: {type(event_data).__name__}")

    event = Event(
        actor_id=user_id,
        object_type=obj.__tablename__,
        object_id=obj.id,
        event_type=event_type,
        event_data=data_dict,
    )
    session.add(event)
    await session.flush()

    logger.info(
        "Event emitted: %s on %s#%s by actor %s",
        event_type.value,
        event.object_type,
        event.object_id,
        user_id,
    )
    return event
