from enum import StrEnum, auto


class EventType(StrEnum):
    """Types of activity events that can be tracked.

    Backs the state-transition log and a generic activity feed (the
    winger-activity feed).
    """

    CREATED = auto()
    UPDATED = auto()
    STATE_CHANGED = auto()
    CUSTOM = auto()
