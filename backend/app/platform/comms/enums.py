from enum import StrEnum, auto


class MessageDirection(StrEnum):
    IN = auto()
    OUT = auto()


class MessageState(StrEnum):
    QUEUED = auto()
    SENT = auto()
    FAILED = auto()
