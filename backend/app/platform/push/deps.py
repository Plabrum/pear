from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config, config
from app.platform.push.client import BasePushClient, build_push_client
from app.platform.push.service import PushService
from app.utils.deps import dep

# Memoize one client per config so the APNsPushClient's cached JWT (and its signer
# state) survives across requests — DI providers are otherwise per-request.
_push_clients: dict[int, BasePushClient] = {}


def _active_config(request: Request) -> Config:
    """The app's active config (shared via state); falls back to the module singleton."""
    return getattr(request.app.state, "config", None) or config


def _push_client_for(cfg: Config) -> BasePushClient:
    client = _push_clients.get(id(cfg))
    if client is None:
        client = build_push_client(cfg)
        _push_clients[id(cfg)] = client
    return client


@dep("push", sync_to_thread=False)
def provide_push(request: Request, transaction: AsyncSession) -> PushService:
    return PushService(_push_client_for(_active_config(request)), transaction, request)
