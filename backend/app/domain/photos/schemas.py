"""msgspec schemas for the photos domain.

Ported from `supabase/functions/api/domains/photos/schemas.ts`. Field names are
camelCase to match the Hono Zod output byte-for-byte — the mobile app's Orval hooks
consume these.

Output structs:
    PhotoSuggesterRef / Photo      — a photo on a dating profile (+ optional suggester ref)
    OwnPhotosResponse              — list[Photo] returned by GET /photos/me
    PhotosOkResponse               — `{ ok: true }` returned by reject / delete
    PhotoUploadUrlResponse         — `{ path, uploadToken }` (storage is Phase 6)

Input structs (consumed by the actions layer):
    CreatePhotoData                — POST /photos body
    ReorderPhotoData               — PATCH /photos/{id}/reorder body
    PhotoUploadUrlData             — POST /photos/upload-url body
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from app.platform.base.schemas import BaseSchema

# ── Output ───────────────────────────────────────────────────────────────────


class PhotoSuggesterRef(BaseSchema):
    id: UUID
    chosenName: str | None


class Photo(BaseSchema):
    id: UUID
    datingProfileId: UUID
    storageUrl: str
    displayOrder: int
    approvedAt: str | None
    suggesterId: UUID | None
    suggester: PhotoSuggesterRef | None


# GET /photos/me returns a bare JSON array of photos.
OwnPhotosResponse = list[Photo]


class PhotosOkResponse(BaseSchema):
    """`{ ok: true }` — reject / delete success body (matches Hono's OkResponse)."""

    ok: Literal[True] = True


class PhotoUploadUrlResponse(BaseSchema):
    path: str
    uploadToken: str


# ── Input ────────────────────────────────────────────────────────────────────


class CreatePhotoData(BaseSchema):
    """POST /photos body — create photo metadata (dater or active wingperson)."""

    datingProfileId: UUID
    storageUrl: str
    displayOrder: int


class ReorderPhotoData(BaseSchema):
    """PATCH /photos/{id}/reorder body."""

    displayOrder: int


class PhotoUploadUrlData(BaseSchema):
    """POST /photos/upload-url body — request a presigned upload (storage Phase 6)."""

    datingProfileId: UUID
    filename: str
