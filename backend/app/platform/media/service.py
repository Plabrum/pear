from __future__ import annotations

import uuid
from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.media.client import BaseMediaClient
from app.platform.media.enums import MediaState
from app.platform.media.models import Media
from app.platform.media.queries import fetch_media_by_ids

# Image extensions we accept on an upload key. Anything else falls back to jpg.
_ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}


def _ext_from_filename(filename: str) -> str:
    """The lowercased extension after the last dot, allowlisted to image types.

    A hostile filename cannot smuggle an arbitrary suffix into the storage key.
    """
    dot = filename.rfind(".")
    if 0 < dot < len(filename) - 1:
        ext = filename[dot + 1 :].lower()
        if ext in _ALLOWED_EXTS:
            return ext
    return "jpg"


def build_media_key(owner_id: UUID, filename: str) -> str:
    """`<ownerId>/<uuid>.<ext>` — the original upload, rooted in the owner's folder."""
    return f"{owner_id}/{uuid.uuid4()}.{_ext_from_filename(filename)}"


class MediaService:
    """Session-bound helpers for creating media + resolving servable URLs."""

    def __init__(self, transaction: AsyncSession, client: BaseMediaClient) -> None:
        self.transaction = transaction
        self.client = client

    async def create_for_owner(self, owner_id: UUID, *, file_name: str, mime_type: str) -> Media:
        """Create a PENDING Media owned by `owner_id` and return it (flushed for its id).

        The caller is responsible for authorizing `owner_id` (the route only ever
        passes the authenticated caller's own id).
        """
        media = Media(
            owner_id=owner_id,
            file_key=build_media_key(owner_id, file_name),
            processed_key=None,
            mime_type=mime_type,
            file_name=file_name,
        )
        self.transaction.add(media)
        await self.transaction.flush()
        return media

    def _servable_key(self, media: Media) -> str:
        """The processed key once READY, otherwise the original (a sane fallback)."""
        if media.state == MediaState.READY and media.processed_key:
            return media.processed_key
        return media.file_key

    async def resolve_url(self, media: Media) -> str:
        """A short-lived presigned GET URL for the best servable key of `media`."""
        return await self.client.presign_download(self._servable_key(media))

    async def resolve_urls(self, media: Sequence[Media]) -> dict[UUID, str]:
        """Batch-resolve `{media.id: url}` for already-loaded, already-authorized rows."""
        return {m.id: await self.resolve_url(m) for m in media}

    async def resolve_urls_system(self, media_ids: Sequence[UUID]) -> dict[UUID, str]:
        """Resolve URLs for `media_ids` under `app.is_system_mode = true`.

        The photos domain calls this AFTER it has authorized that the viewer may see
        the underlying (approved) photo — media RLS alone would not let a matched
        viewer SELECT the owner's media row. We flip on the honored system escape for
        the duration of the read, presign each row, then restore ordinary scope so no
        elevated state leaks into the rest of the request.
        """
        await self.transaction.execute(text("SET LOCAL app.is_system_mode = true"))
        try:
            rows = await fetch_media_by_ids(self.transaction, media_ids)
            return {m.id: await self.resolve_url(m) for m in rows}
        finally:
            await self.transaction.execute(text("SET LOCAL app.is_system_mode = false"))
