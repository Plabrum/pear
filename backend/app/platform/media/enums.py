from enum import StrEnum, auto


class MediaState(StrEnum):
    """Processing lifecycle of an uploaded media object.

    PENDING    — row created, awaiting the client's direct PUT + the `uploaded` ping.
    PROCESSING — the worker is downloading + re-encoding the original.
    READY      — `processed_key` is written; the normalized file is servable.
    FAILED     — processing errored; the original may still be served as a fallback.
    """

    PENDING = auto()
    PROCESSING = auto()
    READY = auto()
    FAILED = auto()
