from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.platform.media.client import BaseMediaClient
from app.platform.media.enums import MediaState
from app.platform.media.models import Media
from app.platform.media.queries import fetch_media_by_ids
from app.utils.sqids import Sqid

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


def build_media_key(owner_id: int, filename: str) -> str:
    """`<ownerId>/<uuid>.<ext>` — the original upload, rooted in the owner's folder."""
    return f"{owner_id}/{uuid.uuid4()}.{_ext_from_filename(filename)}"


class MediaService:
    """Session-bound helpers for creating media + resolving servable URLs."""

    def __init__(self, transaction: AsyncSession, client: BaseMediaClient) -> None:
        self.transaction = transaction
        self.client = client

    async def create_for_owner(self, owner_id: int, *, file_name: str, mime_type: str) -> Media:
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

    async def resolve_urls(self, media_ids: Sequence[Sqid]) -> dict[Sqid, str]:
        """Resolve `{media.id: url}` for `media_ids`, subject to the caller's RLS scope.

        Reads each media row under the viewer's OWN scope: the media SELECT policy
        lets a viewer read the rows they may legitimately see (their own, ones they
        wing, an approved photo's media on an active dating profile, public avatars),
        so no system mode is required. Ids the viewer cannot see are silently omitted.
        """
        rows = await fetch_media_by_ids(self.transaction, media_ids)
        return {m.id: await self.resolve_url(m) for m in rows}
