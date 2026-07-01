from enum import Enum


class UpdateChannel(Enum):
    PRODUCTION = "production"
    PREVIEW = "preview"


class UpdatePlatform(Enum):
    IOS = "ios"


class RolloutStatus(Enum):
    # Serves this row from `/updates/manifest` — the default state on publish.
    LIVE = "live"
    # Excluded from lookup but not reverted — a manual pause short of a rollback.
    PAUSED = "paused"
    # Instant kill-switch: the next manifest fetch tells the client to fall back
    # to the embedded (build-time) bundle instead of applying this update.
    ROLLED_BACK = "rolled_back"
