from __future__ import annotations

from datetime import date, datetime

from app.domain.dating_profiles.models import DatingProfile
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile as ProfileModel
from app.domain.profiles.schemas import (
    OwnDatingProfile,
    OwnProfilePhoto,
    OwnProfilePrompt,
    OwnPromptResponse,
    PhotoSuggester,
    Profile,
    PromptResponseAuthor,
    PromptTemplateRef,
    PublicDatingProfile,
    PublicProfile,
    PublicProfilePhoto,
    PublicProfilePrompt,
)
from app.domain.prompts.models import ProfilePrompt, PromptResponse
from app.platform.media.client import BaseMediaClient


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _avatar_url(key: str | None, media: BaseMediaClient) -> str | None:
    """Resolve an avatar key to its public-read URL (avatars are public; no presign)."""
    return media.public_url(key) if key else None


def row_to_profile(row: ProfileModel, media: BaseMediaClient) -> Profile:
    return Profile(
        id=row.id,
        chosenName=row.chosen_name,
        avatarUrl=_avatar_url(row.avatar_url, media),
        phoneNumber=row.phone_number,
        dateOfBirth=_iso(row.date_of_birth),
        gender=row.gender,
        role=row.role,
        pushToken=row.push_token,
    )


async def _photo_to_own(photo: ProfilePhoto, suggester_name: str | None, media: BaseMediaClient) -> OwnProfilePhoto:
    return OwnProfilePhoto(
        id=photo.id,
        storageUrl=await media.presign_download(photo.storage_url),
        displayOrder=photo.display_order,
        approvedAt=_iso(photo.approved_at),
        suggesterId=photo.suggester_id,
        suggester=(
            PhotoSuggester(id=photo.suggester_id, chosenName=suggester_name) if photo.suggester_id is not None else None
        ),
    )


def _prompt_to_own(
    prompt: ProfilePrompt,
    question: str,
    responses: list[tuple[PromptResponse, ProfileModel | None]],
    media: BaseMediaClient,
) -> OwnProfilePrompt:
    return OwnProfilePrompt(
        id=prompt.id,
        answer=prompt.answer,
        createdAt=_iso(prompt.created_at) or "",
        template=PromptTemplateRef(id=prompt.prompt_template_id, question=question),
        responses=[
            OwnPromptResponse(
                id=response.id,
                message=response.message,
                isApproved=response.is_approved,
                userId=response.user_id,
                createdAt=_iso(response.created_at) or "",
                author=(
                    PromptResponseAuthor(
                        id=author.id,
                        chosenName=author.chosen_name,
                        avatarUrl=_avatar_url(author.avatar_url, media),
                    )
                    if author is not None
                    else None
                ),
            )
            for response, author in responses
        ],
    )


def compute_ripeness(
    photos: list[OwnProfilePhoto],
    prompts: list[OwnProfilePrompt],
    bio: str | None,
    interests: list,
    city: object,
) -> int:
    """A 0-100 profile-completeness score."""
    approved_photos = [p for p in photos if p.approvedAt is not None]
    photo_score = min(len(approved_photos) / 6, 1) * 30
    prompt_score = min(len(prompts) / 3, 1) * 25
    bio_score = 20 if bio else 0
    interest_score = 15 if len(interests) > 0 else 0
    city_score = 10 if city else 0
    return round(photo_score + prompt_score + bio_score + interest_score + city_score)


# A loaded bundle: the dating profile plus the joined photo/prompt/response data.
# Photos: list of (ProfilePhoto, suggester chosen_name | None).
# Prompts: list of (ProfilePrompt, template question, [(PromptResponse, author | None)]).
PhotoBundle = list[tuple[ProfilePhoto, str | None]]
ResponseBundle = list[tuple[PromptResponse, ProfileModel | None]]
PromptBundle = list[tuple[ProfilePrompt, str, ResponseBundle]]


async def dating_profile_to_own(
    base: DatingProfile,
    photos: PhotoBundle,
    prompts: PromptBundle,
    media: BaseMediaClient,
) -> OwnDatingProfile:
    mapped_photos = [await _photo_to_own(photo, name, media) for photo, name in photos]
    mapped_prompts = [_prompt_to_own(p, q, r, media) for p, q, r in prompts]
    return OwnDatingProfile(
        id=base.id,
        userId=base.user_id,
        bio=base.bio,
        city=base.city,
        interestedGender=list(base.interested_gender),
        ageFrom=base.age_from,
        ageTo=base.age_to,
        religion=base.religion,
        religiousPreference=base.religious_preference,
        interests=list(base.interests),
        isActive=base.is_active,
        datingStatus=base.dating_status,
        createdAt=_iso(base.created_at) or "",
        updatedAt=_iso(base.updated_at) or "",
        photos=mapped_photos,
        prompts=mapped_prompts,
        ripeness=compute_ripeness(mapped_photos, mapped_prompts, base.bio, list(base.interests), base.city),
    )


async def bundle_to_public_profile(
    profile: ProfileModel,
    base: DatingProfile | None,
    photos: PhotoBundle,
    prompts: PromptBundle,
    media: BaseMediaClient,
) -> PublicProfile:
    # The query already restricts a public bundle to APPROVED photos, so presigning
    # every one here cannot leak a pending/rejected image.
    public_photos = [
        PublicProfilePhoto(
            id=photo.id,
            storageUrl=await media.presign_download(photo.storage_url),
            displayOrder=photo.display_order,
            approvedAt=_iso(photo.approved_at),
            suggesterId=photo.suggester_id,
        )
        for photo, _ in photos
    ]
    return PublicProfile(
        id=profile.id,
        chosenName=profile.chosen_name,
        avatarUrl=_avatar_url(profile.avatar_url, media),
        datingProfile=(
            PublicDatingProfile(
                id=base.id,
                bio=base.bio,
                city=base.city,
                interests=list(base.interests),
                religion=base.religion,
                photos=public_photos,
                prompts=[
                    PublicProfilePrompt(
                        id=prompt.id,
                        answer=prompt.answer,
                        createdAt=_iso(prompt.created_at) or "",
                        template=PromptTemplateRef(id=prompt.prompt_template_id, question=question),
                    )
                    for prompt, question, _ in prompts
                ],
            )
            if base is not None
            else None
        ),
    )
