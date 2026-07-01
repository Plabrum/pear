"""Push service dependency provider (STUB)."""

from app.platform.push.service import PushService
from app.utils.deps import dep


@dep("push", sync_to_thread=False)
def provide_push() -> PushService:
    return PushService()
