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
from app.platform.actions.base import ActionGroup
from app.platform.actions.deps import ActionDeps
from app.platform.actions.hydrate import actions_for
from app.utils.sqids import Sqid

# `url_by_media` maps a Media id -> its resolved (presigned/public) URL. The route
# batches one MediaService resolve over every avatar + photo media id, then hands
# the map down so the mappers stay synchronous and do no I/O.
UrlByMedia = dict[Sqid, str]


def _iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _resolve(media_id: Sqid | None, url_by_media: UrlByMedia) -> str | None:
    """A Media id -> its resolved URL (or None when absent/unresolved)."""
    return url_by_media.get(media_id) if media_id is not None else None


def row_to_profile(row: ProfileModel, url_by_media: UrlByMedia, group: ActionGroup, deps: ActionDeps) -> Profile:
    dto = Profile(
        id=row.id,
        chosenName=row.chosen_name,
        avatarUrl=_resolve(row.avatar_media_id, url_by_media),
        phoneNumber=row.phone_number,
        dateOfBirth=_iso(row.date_of_birth),
        gender=row.gender,
        role=row.role,
        pushToken=row.push_token,
    )
    dto.actions = actions_for(group, deps, row)
    return dto


def _photo_to_own(
    photo: ProfilePhoto,
    suggester_name: str | None,
    url_by_media: UrlByMedia,
    photo_group: ActionGroup,
    deps: ActionDeps,
) -> OwnProfilePhoto:
    dto = OwnProfilePhoto(
        id=photo.id,
        storageUrl=_resolve(photo.media_id, url_by_media) or "",
        displayOrder=photo.display_order,
        approvedAt=_iso(photo.approved_at),
        suggesterId=photo.suggester_id,
        suggester=(
            PhotoSuggester(id=photo.suggester_id, chosenName=suggester_name) if photo.suggester_id is not None else None
        ),
    )
    dto.actions = actions_for(photo_group, deps, photo)
    return dto


def _prompt_to_own(
    prompt: ProfilePrompt,
    question: str,
    responses: list[tuple[PromptResponse, ProfileModel | None]],
    url_by_media: UrlByMedia,
    prompt_group: ActionGroup,
    response_group: ActionGroup,
    deps: ActionDeps,
) -> OwnProfilePrompt:
    mapped_responses: list[OwnPromptResponse] = []
    for response, author in responses:
        response_dto = OwnPromptResponse(
            id=response.id,
            message=response.message,
            isApproved=response.is_approved,
            userId=response.user_id,
            createdAt=_iso(response.created_at) or "",
            author=(
                PromptResponseAuthor(
                    id=author.id,
                    chosenName=author.chosen_name,
                    avatarUrl=_resolve(author.avatar_media_id, url_by_media),
                )
                if author is not None
                else None
            ),
        )
        response_dto.actions = actions_for(response_group, deps, response)
        mapped_responses.append(response_dto)
    dto = OwnProfilePrompt(
        id=prompt.id,
        answer=prompt.answer,
        createdAt=_iso(prompt.created_at) or "",
        template=PromptTemplateRef(id=prompt.prompt_template_id, question=question),
        responses=mapped_responses,
    )
    dto.actions = actions_for(prompt_group, deps, prompt)
    return dto


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


def own_media_ids(photos: PhotoBundle, prompts: PromptBundle) -> list[Sqid]:
    """Every Media id referenced by an own-dating-profile bundle (photos + author avatars)."""
    ids: list[Sqid] = [photo.media_id for photo, _ in photos]
    for _, _, responses in prompts:
        ids.extend(author.avatar_media_id for _, author in responses if author and author.avatar_media_id)
    return ids


def public_media_ids(profile: ProfileModel, photos: PhotoBundle) -> list[Sqid]:
    """Every Media id referenced by a public-profile bundle (avatar + approved photos)."""
    ids: list[Sqid] = [photo.media_id for photo, _ in photos]
    if profile.avatar_media_id is not None:
        ids.append(profile.avatar_media_id)
    return ids


def dating_profile_to_own(
    base: DatingProfile,
    photos: PhotoBundle,
    prompts: PromptBundle,
    url_by_media: UrlByMedia,
    dating_profile_group: ActionGroup,
    photo_group: ActionGroup,
    prompt_group: ActionGroup,
    response_group: ActionGroup,
    deps: ActionDeps,
) -> OwnDatingProfile:
    mapped_photos = [_photo_to_own(photo, name, url_by_media, photo_group, deps) for photo, name in photos]
    mapped_prompts = [_prompt_to_own(p, q, r, url_by_media, prompt_group, response_group, deps) for p, q, r in prompts]
    dto = OwnDatingProfile(
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
    # base -> DATING_PROFILE_ACTIONS (the EDIT group, not the swipe group).
    dto.actions = actions_for(dating_profile_group, deps, base)
    return dto


def bundle_to_public_profile(
    profile: ProfileModel,
    base: DatingProfile | None,
    photos: PhotoBundle,
    prompts: PromptBundle,
    url_by_media: UrlByMedia,
    swipe_group: ActionGroup,
    deps: ActionDeps,
) -> PublicProfile:
    # The query already restricts a public bundle to APPROVED photos, so resolving
    # every one here cannot leak a pending/rejected image.
    public_photos = [
        PublicProfilePhoto(
            id=photo.id,
            storageUrl=_resolve(photo.media_id, url_by_media) or "",
            displayOrder=photo.display_order,
            approvedAt=_iso(photo.approved_at),
            suggesterId=photo.suggester_id,
        )
        for photo, _ in photos
    ]
    dating_profile: PublicDatingProfile | None = None
    if base is not None:
        dating_profile = PublicDatingProfile(
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
        # The swipe group is bound to DatingProfile, so its actions (like/pass/
        # suggest/decline/report) belong on the nested PublicDatingProfile.
        dating_profile.actions = actions_for(swipe_group, deps, base)
    return PublicProfile(
        id=profile.id,
        chosenName=profile.chosen_name,
        avatarUrl=_resolve(profile.avatar_media_id, url_by_media),
        datingProfile=dating_profile,
    )
