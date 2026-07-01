import io
import logging
from pathlib import PurePosixPath
from uuid import UUID

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.media.client import build_media_client
from app.platform.media.enums import MediaState
from app.platform.media.models import Media
from app.platform.media.state_machine import media_machine
from app.platform.queue.enums import TaskName, TaskRoleType
from app.platform.queue.registry import task
from app.platform.queue.transactions import with_transaction
from app.platform.queue.types import AppContext
from app.platform.state_machine.machine import StateMachineService

logger = logging.getLogger(__name__)


def _processed_key(file_key: str, image_format: str) -> str:
    """`<key-stem>.<format>` — same folder + stem as the original, new extension."""
    p = PurePosixPath(file_key)
    return str(p.with_suffix(f".{image_format}"))


def _reencode(data: bytes, image_format: str, quality: int) -> bytes:
    """Decode `data`, normalize mode (RGB / RGBA for alpha), re-encode to `image_format`.

    No resize and no thumbnail: the client already resizes; this only normalizes the
    container format (e.g. HEIC/JPEG/PNG -> WebP).
    """
    with Image.open(io.BytesIO(data)) as img:
        target_mode = "RGBA" if img.mode in {"RGBA", "LA", "P"} and "transparency" in img.info else "RGB"
        converted = img.convert(target_mode)
        out = io.BytesIO()
        converted.save(out, format=image_format.upper(), quality=quality)
        return out.getvalue()


# NOTE: the function name MUST match TaskName.PROCESS_IMAGE's value ("process_image").
# SAQ identifies tasks by __qualname__, which doubles as the pickle re-import path
# under the `spawn` start method, so a mismatched name crashes the worker.
@task(TaskName.PROCESS_IMAGE)
@with_transaction(role_type=TaskRoleType.SYSTEM)
async def process_image(
    ctx: AppContext,
    *,
    transaction: AsyncSession,
    media_id: str,
) -> None:
    """Normalize an uploaded image to WebP and drive the Media state machine.

    PENDING -> PROCESSING, download the original, re-encode to the configured format,
    upload the result, write `processed_key`, then PROCESSING -> READY. Any failure
    is logged and swallowed (state -> FAILED) so a bad upload never crashes the worker.
    """
    config = ctx["config"]
    media = await transaction.get(Media, UUID(media_id))
    if media is None:
        logger.error("[media] process_image: media %s not found", media_id)
        return

    sm = StateMachineService(transaction)
    image_format = config.MEDIA_IMAGE_FORMAT
    quality = config.MEDIA_WEBP_QUALITY
    # Worker-injected client (set at queue startup); build one if absent (sync dispatch).
    client = ctx.get("media_client") or build_media_client(config)

    try:
        await sm.system_transition(media_machine, media, MediaState.PROCESSING)
        original = await client.download(media.file_key)
        encoded = _reencode(original, image_format, quality)
        processed_key = _processed_key(media.file_key, image_format)
        await client.upload(processed_key, encoded, content_type=f"image/{image_format}")
        media.processed_key = processed_key
        await sm.system_transition(media_machine, media, MediaState.READY)
    except Exception:
        logger.exception("[media] process_image failed for media %s", media_id)
        # Best-effort FAILED transition; never re-raise (would crash/retry the worker).
        try:
            await sm.system_transition(media_machine, media, MediaState.FAILED)
        except Exception:
            logger.exception("[media] could not mark media %s FAILED", media_id)
