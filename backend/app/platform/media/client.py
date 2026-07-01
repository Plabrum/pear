from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

import aioboto3

from app.config import Config

logger = logging.getLogger(__name__)


class MediaError(Exception):
    """Raised when the media backend cannot produce a presigned URL."""


@dataclass(frozen=True)
class PresignedUpload:
    """A presigned PUT target the client uploads bytes to directly.

    `upload_url` — PUT here with the raw image bytes and matching `Content-Type`.
    `key`        — the S3 object key persisted as the Media row's `file_key`.
    """

    upload_url: str
    key: str


# Reads default to image/jpeg (the client resizes to JPEG before upload —
# expo-image-manipulator, max 1200px / q0.8 / JPEG).
DEFAULT_CONTENT_TYPE = "image/jpeg"


class BaseMediaClient(ABC):
    """Object-storage contract for user media (photos + avatars)."""

    @abstractmethod
    async def presign_upload(self, key: str, *, content_type: str = DEFAULT_CONTENT_TYPE) -> PresignedUpload:
        """Mint a presigned PUT URL for `key`. The caller authorizes first."""

    @abstractmethod
    async def presign_download(self, key: str) -> str:
        """Issue a short-lived presigned GET URL for a private object (`key`).

        The caller must have already RLS-checked the requester's right to read it.
        """

    @abstractmethod
    def public_url(self, key: str) -> str:
        """Resolve a public-read object (avatar) to a stable URL. No presign."""

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete an object. Log-and-swallow: a failed delete leaks one object,
        never a broken DB reference."""

    @abstractmethod
    async def download(self, key: str) -> bytes:
        """Fetch the raw bytes of an object by `key`. Used by the image-processing
        worker to read the original upload. Raises `MediaError` on failure."""

    @abstractmethod
    async def upload(self, key: str, data: bytes, *, content_type: str) -> None:
        """Write raw bytes to `key` with the given content type. Used by the worker
        to store the processed (re-encoded) image. Raises `MediaError` on failure."""


class S3Client(BaseMediaClient):
    """Production S3-backed media client (aioboto3, private bucket)."""

    def __init__(self, config: Config) -> None:
        self.bucket = config.S3_MEDIA_BUCKET
        self.region = config.AWS_REGION
        self.ttl = config.S3_PRESIGN_TTL_SECONDS
        # Public read base (CloudFront / bucket public endpoint). Falls back to the
        # regional virtual-hosted URL when unset (works for a public-read object).
        self._public_base = config.S3_PUBLIC_BASE_URL.rstrip("/") or (
            f"https://{self.bucket}.s3.{self.region}.amazonaws.com"
        )
        self._session = aioboto3.Session()

    async def presign_upload(self, key: str, *, content_type: str = DEFAULT_CONTENT_TYPE) -> PresignedUpload:
        async with self._session.client("s3", region_name=self.region) as s3:  # type: ignore[attr-defined]
            try:
                url = await s3.generate_presigned_url(
                    "put_object",
                    Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
                    ExpiresIn=self.ttl,
                )
            except Exception as exc:  # noqa: BLE001 — surface as our typed error
                logger.error("[media] presign_upload failed: key=%s err=%s", key, exc)
                raise MediaError("Could not create upload URL") from exc
        return PresignedUpload(upload_url=url, key=key)

    async def presign_download(self, key: str) -> str:
        async with self._session.client("s3", region_name=self.region) as s3:  # type: ignore[attr-defined]
            try:
                return await s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self.bucket, "Key": key},
                    ExpiresIn=self.ttl,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("[media] presign_download failed: key=%s err=%s", key, exc)
                raise MediaError("Could not create download URL") from exc

    def public_url(self, key: str) -> str:
        return f"{self._public_base}/{key}"

    async def delete(self, key: str) -> None:
        try:
            async with self._session.client("s3", region_name=self.region) as s3:  # type: ignore[attr-defined]
                await s3.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001 — log-and-swallow
            logger.error("[media] delete failed: key=%s err=%s", key, exc)

    async def download(self, key: str) -> bytes:
        async with self._session.client("s3", region_name=self.region) as s3:  # type: ignore[attr-defined]
            try:
                obj = await s3.get_object(Bucket=self.bucket, Key=key)
                async with obj["Body"] as body:
                    return await body.read()
            except Exception as exc:  # noqa: BLE001 — surface as our typed error
                logger.error("[media] download failed: key=%s err=%s", key, exc)
                raise MediaError("Could not download object") from exc

    async def upload(self, key: str, data: bytes, *, content_type: str) -> None:
        async with self._session.client("s3", region_name=self.region) as s3:  # type: ignore[attr-defined]
            try:
                await s3.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)
            except Exception as exc:  # noqa: BLE001
                logger.error("[media] upload failed: key=%s err=%s", key, exc)
                raise MediaError("Could not upload object") from exc


class LocalMediaClient(BaseMediaClient):
    """Local/test fake: deterministic fake URLs, no AWS.

    Returns predictable, well-formed URLs so presign-endpoint tests can assert the
    shape (a PUT target + the key) and read-gating tests can assert which keys get
    a URL — all without touching S3. Deletes are recorded in `deleted` for tests
    that want to assert the side effect.
    """

    def __init__(self, config: Config) -> None:
        self.bucket = config.S3_MEDIA_BUCKET
        self.ttl = config.S3_PRESIGN_TTL_SECONDS
        self._base = config.LOCAL_MEDIA_BASE_URL.rstrip("/")
        self._public_base = config.S3_PUBLIC_BASE_URL.rstrip("/") or f"{self._base}/public"
        self.deleted: list[str] = []
        # In-memory object store so download/upload round-trip in tests with no S3.
        # Keyed by object key -> (bytes, content_type).
        self.store: dict[str, tuple[bytes, str]] = {}

    async def presign_upload(self, key: str, *, content_type: str = DEFAULT_CONTENT_TYPE) -> PresignedUpload:
        # A deterministic PUT target a fake/dev client can no-op against.
        url = f"{self._base}/upload/{self.bucket}/{key}?expires={self.ttl}&content-type={content_type}"
        return PresignedUpload(upload_url=url, key=key)

    async def presign_download(self, key: str) -> str:
        return f"{self._base}/download/{self.bucket}/{key}?expires={self.ttl}"

    def public_url(self, key: str) -> str:
        return f"{self._public_base}/{key}"

    async def delete(self, key: str) -> None:
        self.deleted.append(key)
        self.store.pop(key, None)
        logger.info("[media] LOCAL delete (not real): key=%s", key)

    async def download(self, key: str) -> bytes:
        entry = self.store.get(key)
        if entry is None:
            raise MediaError(f"Could not download object (no local bytes for {key})")
        return entry[0]

    async def upload(self, key: str, data: bytes, *, content_type: str) -> None:
        self.store[key] = (data, content_type)


def build_media_client(config: Config) -> BaseMediaClient:
    """Local fake in local/dev/testing; real S3 otherwise (mirrors build_apple_verifier)."""
    if config.ENV in {"development", "local", "testing"}:
        return LocalMediaClient(config)
    return S3Client(config)
