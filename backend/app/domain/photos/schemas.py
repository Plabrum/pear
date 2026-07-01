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


# ── GET /photos/suggested (photos I suggested as a winger) ───────────────────────

SuggestedPhotoStatus = Literal["approved", "pending", "not_accepted"]


class SuggestedPhoto(BaseSchema):
    """A photo the caller suggested for a dater, with that dater + the verdict."""

    id: UUID
    daterId: UUID
    daterName: str
    storageUrl: str
    status: SuggestedPhotoStatus
    createdAt: str


# GET /photos/suggested returns a bare JSON array.
SuggestedPhotosResponse = list[SuggestedPhoto]


class PhotosOkResponse(BaseSchema):
    """`{ ok: true }` — reject / delete success body."""

    ok: Literal[True] = True


# ── Input ────────────────────────────────────────────────────────────────────


class CreatePhotoData(BaseSchema):
    """POST /photos body — link a Media to a dating profile (dater or active wingperson).

    `mediaId` references a platform Media the caller already created+uploaded via
    POST /media/upload-url + POST /media/{id}/uploaded. No S3 keys cross this domain."""

    datingProfileId: UUID
    mediaId: UUID
    displayOrder: int


class ReorderPhotoData(BaseSchema):
    """PATCH /photos/{id}/reorder body."""

    displayOrder: int
