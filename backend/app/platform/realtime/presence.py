from __future__ import annotations

import logging
from collections import defaultdict

logger = logging.getLogger(__name__)


class PresenceRegistry:
    """In-process, reference-counted set of online user ids."""

    def __init__(self) -> None:
        self._counts: dict[int, int] = defaultdict(int)

    def connect(self, user_id: int) -> bool:
        """Register a socket for `user_id`. Returns True if this is a NEW arrival
        (the user transitioned offline -> online), so the caller can broadcast a
        single join event rather than one per socket."""
        was_offline = self._counts[user_id] == 0
        self._counts[user_id] += 1
        return was_offline

    def disconnect(self, user_id: int) -> bool:
        """Drop a socket for `user_id`. Returns True if the user is now FULLY offline
        (no remaining sockets), so the caller can broadcast a single leave event."""
        current = self._counts.get(user_id, 0)
        if current <= 1:
            self._counts.pop(user_id, None)
            return current == 1  # 1 -> 0 is a real departure; 0 -> 0 is a no-op
        self._counts[user_id] = current - 1
        return False

    def is_online(self, user_id: int) -> bool:
        return self._counts.get(user_id, 0) > 0

    def online_ids(self, *, excluding: int | None = None) -> set[int]:
        ids = {uid for uid, n in self._counts.items() if n > 0}
        if excluding is not None:
            ids.discard(excluding)
        return ids


# Single process-wide registry. Imported by the realtime deps + ws route.
presence_registry = PresenceRegistry()
