from __future__ import annotations

from dataclasses import dataclass

from app.domain.dating_profiles.enums import City, DatingStatus, Interest
from app.domain.dating_profiles.models import DatingProfile
from app.domain.dating_profiles.schemas import SwipeProfile, WingSuggestion
from app.domain.profiles.enums import Gender
from app.platform.actions.base import ActionGroup
from app.platform.actions.deps import ActionDeps
from app.platform.actions.hydrate import actions_for
from app.platform.media.client import BaseMediaClient
from app.utils.sqids import Sqid


@dataclass
class WingSuggestionRow:
    winger_id: Sqid
    winger_name: str | None
    note: str | None


@dataclass
class SwipeRow:
    profile_id: Sqid
    user_id: Sqid
    chosen_name: str
    gender: Gender | None
    age: int
    city: City
    bio: str | None
    dating_status: DatingStatus
    interests: list[Interest]
    photos: list[str]  # S3 keys (approved only) — presigned at transform time
    suggestions: list[WingSuggestionRow]


async def row_to_swipe_profile(
    row: SwipeRow,
    media: BaseMediaClient,
    group: ActionGroup,
    deps: ActionDeps,
) -> SwipeProfile:
    # `photos` are approved-only S3 keys (the query filters approved_at IS NOT NULL),
    # so presigning each one cannot leak an unapproved image.
    photos = [await media.presign_download(key) for key in (row.photos or [])]
    profile = SwipeProfile(
        profileId=row.profile_id,
        userId=row.user_id,
        chosenName=row.chosen_name,
        gender=row.gender,
        age=row.age,
        city=row.city,
        bio=row.bio,
        datingStatus=row.dating_status,
        interests=row.interests,
        photos=photos,
        # `firstPhoto` mirrors the former likes-you / wing-pool single-photo field.
        firstPhoto=photos[0] if photos else None,
        suggestions=[
            WingSuggestion(wingerId=s.winger_id, wingerName=s.winger_name, note=s.note) for s in row.suggestions
        ],
    )
    # The swipe read is a pure projection — no DatingProfile ORM row is in hand. The
    # swipe group's `is_available` reads ONLY scalar identity columns (obj.user_id) +
    # the principal, never a relationship, so a transient stub carrying just the
    # profile + owner identity is a safe gating arg. NOT added to the session.
    stub = DatingProfile(id=row.profile_id, user_id=row.user_id)
    profile.actions = actions_for(group, deps, stub)
    return profile
