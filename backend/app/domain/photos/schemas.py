from __future__ import annotations

from typing import Literal

from app.domain.photos.enums import PhotoApprovalState
from app.platform.actions.schemas import Actionable
from app.platform.base.schemas import BaseSchema
from app.utils.sqids import Sqid

# ── Output ───────────────────────────────────────────────────────────────────


class PhotoSuggesterRef(BaseSchema):
    id: Sqid
    chosenName: str | None


class Photo(Actionable):
    id: Sqid
    datingProfileId: Sqid
    storageUrl: str
    displayOrder: int
    # The approval lifecycle as an explicit literal (pending|approved|rejected) —
    # the single uniform status the client reads, mirroring the backend `state`.
    status: PhotoApprovalState
    suggesterId: Sqid | None
    suggester: PhotoSuggesterRef | None


# GET /photos/me returns a bare JSON array of photos.
OwnPhotosResponse = list[Photo]


# ── GET /photos/suggested (photos I suggested as a winger) ───────────────────────

SuggestedPhotoStatus = Literal["approved", "pending", "not_accepted"]


class SuggestedPhoto(BaseSchema):
    """A photo the caller suggested for a dater, with that dater + the verdict."""

    id: Sqid
    daterId: Sqid
    daterName: str
    storageUrl: str
    status: SuggestedPhotoStatus
    createdAt: str


# GET /photos/suggested returns a bare JSON array.
SuggestedPhotosResponse = list[SuggestedPhoto]


# ── Input ────────────────────────────────────────────────────────────────────


class CreatePhotoData(BaseSchema):
    """POST /photos body — link a Media to a dating profile (dater or active wingperson).

    `mediaId` references a platform Media the caller already created+uploaded via
    POST /media/upload-url + POST /media/{id}/uploaded. No S3 keys cross this domain."""

    datingProfileId: Sqid
    mediaId: Sqid
    displayOrder: int


class ReorderPhotoData(BaseSchema):
    """PATCH /photos/{id}/reorder body."""

    displayOrder: int
