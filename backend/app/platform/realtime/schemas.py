from __future__ import annotations

from app.platform.base.schemas import BaseSchema

# ── Server -> client frames ────────────────────────────────────────────────────


class ReadyFrame(BaseSchema):
    type: str = "ready"


class SubscribedFrame(BaseSchema):
    channel: str
    type: str = "subscribed"


class UnsubscribedFrame(BaseSchema):
    channel: str
    type: str = "unsubscribed"


class PongFrame(BaseSchema):
    type: str = "pong"


class ErrorFrame(BaseSchema):
    message: str
    channel: str | None = None
    type: str = "error"


class TypingPayload(BaseSchema):
    userId: str
    ts: int


# NOTE: `message` and `presence` frames are emitted by the RealtimeService (see
# service.py) as plain dicts so the already-serialized `Message` struct / id lists
# pass straight through the channels backend. Keeping them as dicts avoids a second
# struct round-trip on a hot path. Their shape is reproduced in service.py's builders.
