from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.platform.media.client import BaseMediaClient, build_media_client
from app.platform.media.service import MediaService
from app.utils.deps import dep


def _active_config(request: Request):
    """The app's active config (shared via state). Mirrors auth.deps._active_config."""
    return getattr(request.app.state, "config", None) or config


@dep("media", sync_to_thread=False)
def provide_media_client(request: Request) -> BaseMediaClient:
    """Object-storage client: LocalMediaClient in dev/test, S3Client in prod."""
    return build_media_client(_active_config(request))


@dep("media_service", sync_to_thread=False)
def provide_media_service(transaction: AsyncSession, media: BaseMediaClient) -> MediaService:
    """Request-scoped MediaService bound to the transaction + storage client."""
    return MediaService(transaction, media)
