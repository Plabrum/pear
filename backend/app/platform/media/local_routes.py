# Dev/test-only HTTP sink for the `LocalMediaClient` presigned URLs.
#
# In prod the presigned PUT/GET URLs point straight at S3. Locally there is no S3, so
# `LocalMediaClient` mints `…/_local-media/…` URLs and these handlers back them with the
# on-disk store (`config.LOCAL_MEDIA_DIR`). The presigned URL is the only grant, so the
# handlers route through the injected media client and are gated to local/test by
# `requires_local` (they reject in prod, never serving real S3). The bucket path segment
# is cosmetic — the client keys storage off `key` alone.

from __future__ import annotations

from pathlib import PurePosixPath

from litestar import Request, Response, Router, get, put
from litestar.exceptions import NotFoundException

from app.platform.auth.guards import requires_local
from app.platform.media.client import BaseMediaClient, MediaError

_CONTENT_TYPE_BY_SUFFIX = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
}


async def _serve(media: BaseMediaClient, key: str) -> Response:
    try:
        content = await media.download(key)
    except MediaError as exc:
        raise NotFoundException(f"No local media at {key}") from exc
    suffix = PurePosixPath(key).suffix.lower()
    media_type = _CONTENT_TYPE_BY_SUFFIX.get(suffix, "application/octet-stream")
    return Response(
        content=content,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000"},
    )


@put("/upload/{bucket:str}/{key:path}", guards=[requires_local], exclude_from_auth=True, status_code=201)
async def local_upload(bucket: str, key: str, request: Request, media: BaseMediaClient) -> dict[str, str]:
    """Receive a raw PUT body and write it to the local media store (mirrors an S3 PUT)."""
    data = await request.body()
    content_type = request.headers.get("content-type", "application/octet-stream")
    await media.upload(key.lstrip("/"), data, content_type=content_type)
    return {"status": "uploaded"}


@get("/download/{bucket:str}/{key:path}", guards=[requires_local], exclude_from_auth=True)
async def local_download(bucket: str, key: str, media: BaseMediaClient) -> Response:
    """Serve a private object back — mirrors an S3 presigned GET."""
    return await _serve(media, key.lstrip("/"))


@get("/public/{key:path}", guards=[requires_local], exclude_from_auth=True)
async def local_public(key: str, media: BaseMediaClient) -> Response:
    """Serve a public-read object (avatars) — no presign, stable URL."""
    return await _serve(media, key.lstrip("/"))


local_media_router = Router(
    path="/_local-media",
    guards=[],
    route_handlers=[local_upload, local_download, local_public],
    tags=["media-local"],
)
