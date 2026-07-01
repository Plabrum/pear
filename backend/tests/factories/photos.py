# Factory for ProfilePhoto (a photo with its approval lifecycle).

from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.models import ProfilePhoto

from .base import BaseFactory


class ProfilePhotoFactory(BaseFactory):
    __model__ = ProfilePhoto

    dating_profile_id = None  # set by the caller
    owner_id = None  # the dating profile's dater — set by the caller
    suggester_id = None  # null = self-uploaded
    media_id = None  # READY media backing the bytes — set by the caller
    display_order = 0
    # Default to an approved, self-uploaded photo; override for winger suggestions.
    state = PhotoApprovalState.APPROVED
    # Audit timestamps are normally written by the state machine's on_enter hooks;
    # factories leave them unset unless a test pins them.
    approved_at = None
    rejected_at = None
