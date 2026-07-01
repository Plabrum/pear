from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.photos.exceptions import (
    DatingProfileNotFoundError,
    NotDaterOrWingpersonError,
)
from app.domain.photos.queries import fetch_dating_profile_owner, is_active_wingperson
from app.domain.photos.schemas import (
    AvatarUploadUrlResponse,
    PhotoUploadUrlResponse,
)
from app.platform.media.client import BaseMediaClient

# Extensions we accept for an image upload. Anything else falls back to jpg (the
# client resizes to JPEG before upload anyway).
_ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp", "heic", "heif"}


def ext_from_filename(filename: str) -> str:
    """The lowercased extension after the last dot, restricted to image types.

    Takes the part after the last dot (else 'jpg') and allowlists the result so a
    hostile filename can't smuggle an arbitrary suffix into the key.
    """
    dot = filename.rfind(".")
    if 0 < dot < len(filename) - 1:
        ext = filename[dot + 1 :].lower()
        if ext in _ALLOWED_EXTS:
            return ext
    return "jpg"


def build_photo_key(owner_id: UUID, filename: str) -> str:
    """`<ownerId>/<uuid>.<ext>` — a profile photo in the owner's folder."""
    return f"{owner_id}/{uuid.uuid4()}.{ext_from_filename(filename)}"


def build_avatar_key(user_id: UUID, filename: str) -> str:
    """`avatars/<userId>/<uuid>.<ext>` — the caller's avatar (public-read prefix)."""
    return f"avatars/{user_id}/{uuid.uuid4()}.{ext_from_filename(filename)}"


# ── Authorize-then-presign flows (Storage-RLS write intent at the endpoint) ──────


async def presign_photo_upload(
    db: AsyncSession,
    *,
    caller_id: UUID,
    dating_profile_id: UUID,
    filename: str,
    content_type: str,
    media: BaseMediaClient,
) -> PhotoUploadUrlResponse:
    """Authorize an own-folder write, then mint a presigned PUT for a profile photo.

    Allowed for the dater-owner OR an active wingperson of that dater. The key is
    rooted in the OWNER's folder, so a winger uploading a suggestion still writes
    into the dater's folder — never their own. Raises:
      * `DatingProfileNotFoundError` (404) — no such dating profile.
      * `NotDaterOrWingpersonError` (403) — caller is neither owner nor a winger.
    """
    owner_id = await fetch_dating_profile_owner(db, dating_profile_id)
    if owner_id is None:
        raise DatingProfileNotFoundError()
    if owner_id != caller_id and not await is_active_wingperson(db, owner_id, caller_id):
        raise NotDaterOrWingpersonError()

    key = build_photo_key(owner_id, filename)
    presigned = await media.presign_upload(key, content_type=content_type)
    return PhotoUploadUrlResponse(uploadUrl=presigned.upload_url, key=presigned.key)


async def presign_avatar_upload(
    *,
    caller_id: UUID,
    filename: str,
    content_type: str,
    media: BaseMediaClient,
) -> AvatarUploadUrlResponse:
    """Mint a presigned PUT for the CALLER's own avatar (public-read key).

    No DB read needed — the key is rooted in the caller's id (`avatars/<userId>/...`),
    so a caller can only ever write their own avatar. `publicUrl` is the stable URL
    the avatar resolves to once the client PATCHes `avatarUrl = key` on its profile.
    """
    key = build_avatar_key(caller_id, filename)
    presigned = await media.presign_upload(key, content_type=content_type)
    return AvatarUploadUrlResponse(
        uploadUrl=presigned.upload_url,
        key=presigned.key,
        publicUrl=media.public_url(presigned.key),
    )
