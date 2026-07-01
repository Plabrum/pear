from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from msgspec import UNSET
from sqlalchemy.ext.asyncio import AsyncSession

# Importing each domain's actions module registers its ActionGroup(s) in the
# singleton ActionRegistry, so `resolve_group(...)` succeeds for every group the
# profiles read paths hydrate (the swipe group on a public profile; the photo /
# prompt / response groups on the own dating-profile bundle).
import app.domain.dating_profiles.actions  # noqa: F401, E402  (registers DATING_PROFILE_SWIPE_ACTIONS)
import app.domain.photos.actions  # noqa: F401, E402  (registers PHOTO_ACTIONS)
import app.domain.prompts.actions  # noqa: F401, E402  (registers PROFILE_PROMPT/PROMPT_RESPONSE_ACTIONS)
from app.domain.dating_profiles.enums import City, DatingStatus, Interest, Religion
from app.domain.profiles.actions import (
    CreateDatingProfile,
    UpdateDatingProfile,
    UpdateProfile,
)
from app.domain.profiles.enums import Gender, UserRole
from app.domain.profiles.exceptions import DatingProfileAlreadyExistsError
from app.domain.profiles.models import Profile as ProfileModel
from app.domain.profiles.queries import (
    fetch_dating_profile_base,
    fetch_own_dating_profile,
    fetch_profile,
    fetch_public_profile,
)
from app.domain.profiles.schemas import (
    CreateDatingProfileData,
    UpdateDatingProfileData,
    UpdateProfileData,
)
from app.domain.profiles.transformers import (
    bundle_to_public_profile,
    compute_ripeness,
    dating_profile_to_own,
    own_media_ids,
    public_media_ids,
    row_to_profile,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import resolve_group
from app.platform.actions.schemas import ActionDTO
from app.platform.auth.principal import User
from app.platform.media.enums import MediaState
from app.platform.media.models import Media
from app.platform.media.service import MediaService
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph
from tests.fixtures.ids import fake_id
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor."""
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=MagicMock(),
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


def _keys(actions: list[ActionDTO]) -> set[str]:
    """The bare action keys (suffix after `<group>__`) surfaced on an Actionable."""
    return {a.action.split("__", 1)[1] for a in actions}


# ── Reads ──────────────────────────────────────────────────────────────────────


async def test_get_own_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    row = await fetch_profile(db_session, graph.dater_a.id)
    assert row is not None
    deps = _deps(db_session, user_id=graph.dater_a.id)
    profile_group = resolve_group(ActionGroupType.PROFILE_ACTIONS)
    dto = row_to_profile(row, {}, profile_group, deps)

    assert dto.id == graph.dater_a.id
    assert dto.chosenName == graph.dater_a.chosen_name
    assert dto.role == UserRole.DATER
    # gender serializes by .value through msgspec -> matches the Zod enum wire form.
    assert dto.gender is Gender.MALE
    # The owner sees the edit action on their own profile row.
    assert _keys(dto.actions) == {"update"}
    update = dto.actions[0]
    assert update.action_group_type == ActionGroupType.PROFILE_ACTIONS


async def test_get_own_profile_actions_empty_for_other_viewer(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A different actor viewing the row gets no actions (UpdateProfile gates on
    # obj.id == user.id). The route only ever serves /profiles/me to the owner, but
    # this proves the hydration honors the gate, not the route.
    row = await fetch_profile(db_session, graph.dater_a.id)
    assert row is not None
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    profile_group = resolve_group(ActionGroupType.PROFILE_ACTIONS)
    dto = row_to_profile(row, {}, profile_group, deps)
    assert dto.actions == []


def _own_dating_profile_groups():
    return (
        resolve_group(ActionGroupType.DATING_PROFILE_ACTIONS),
        resolve_group(ActionGroupType.PHOTO_ACTIONS),
        resolve_group(ActionGroupType.PROFILE_PROMPT_ACTIONS),
        resolve_group(ActionGroupType.PROMPT_RESPONSE_ACTIONS),
    )


async def test_get_own_dating_profile_bundle(graph: DomainGraph, db_session: AsyncSession) -> None:
    bundle = await fetch_own_dating_profile(db_session, graph.dater_a.id)
    assert bundle is not None
    base, photos, prompts = bundle
    url_by_media = await MediaService(db_session, local_media()).resolve_urls(own_media_ids(photos, prompts))
    deps = _deps(db_session, user_id=graph.dater_a.id)
    dp_group, photo_group, prompt_group, response_group = _own_dating_profile_groups()
    dto = dating_profile_to_own(
        base, photos, prompts, url_by_media, dp_group, photo_group, prompt_group, response_group, deps
    )

    assert dto.userId == graph.dater_a.id
    assert dto.city == City.BOSTON
    assert dto.datingStatus == DatingStatus.OPEN
    # graph seeds 1 approved + 1 pending photo, ordered by display_order.
    assert len(dto.photos) == 2
    assert [p.displayOrder for p in dto.photos] == [0, 1]
    approved, pending = dto.photos
    assert approved.approvedAt is not None and approved.suggester is None
    # The approved photo resolved to its READY processed (WebP) media URL.
    assert approved.storageUrl.startswith("http")
    processed_key = graph.approved_media.processed_key
    assert processed_key is not None and processed_key in approved.storageUrl
    assert pending.approvedAt is None and pending.suggesterId == graph.winger.id
    assert pending.suggester is not None
    assert pending.suggester.chosenName == graph.winger.chosen_name
    # 1 prompt with 1 (pending) response carrying its winger author.
    assert len(dto.prompts) == 1
    prompt = dto.prompts[0]
    assert prompt.template.question  # joined template text present
    assert len(prompt.responses) == 1
    resp = prompt.responses[0]
    assert resp.isApproved is False
    assert resp.author is not None and resp.author.id == graph.winger.id
    # ripeness is the documented 0-100 completeness score.
    assert 0 <= dto.ripeness <= 100

    # ── Hydrated actions, viewed as the owning dater ──────────────────────────
    # base -> the EDIT group (DATING_PROFILE_ACTIONS), never the swipe group. The
    # owner sees `update`; `create` is a top-level action so it never rides on a row.
    assert _keys(dto.actions) == {"update"}
    assert all(a.action_group_type == ActionGroupType.DATING_PROFILE_ACTIONS for a in dto.actions)

    # Approved (self-uploaded) photo: owner may only delete it — approve/reject gate
    # on PENDING, reorder is hidden.
    assert _keys(approved.actions) == {"delete"}
    # Pending (winger-suggested) photo: owner may approve / reject / delete it.
    assert _keys(pending.actions) == {"approve", "reject", "delete"}
    assert all(a.action_group_type == ActionGroupType.PHOTO_ACTIONS for a in pending.actions)

    # The owning dater may delete their own prompt.
    assert _keys(prompt.actions) == {"delete"}
    assert all(a.action_group_type == ActionGroupType.PROFILE_PROMPT_ACTIONS for a in prompt.actions)

    # On the pending winger comment the profile owner may approve or delete it.
    assert _keys(resp.actions) == {"approve", "delete"}
    assert all(a.action_group_type == ActionGroupType.PROMPT_RESPONSE_ACTIONS for a in resp.actions)


async def test_get_own_dating_profile_returns_none_when_absent(db_session: AsyncSession) -> None:
    assert await fetch_own_dating_profile(db_session, fake_id()) is None


async def test_get_public_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    bundle = await fetch_public_profile(db_session, graph.dater_b.id)
    assert bundle is not None
    profile, base, photos, prompts = bundle
    url_by_media = await MediaService(db_session, local_media()).resolve_urls(public_media_ids(profile, photos))
    dto = bundle_to_public_profile(
        profile,
        base,
        photos,
        prompts,
        url_by_media,
        resolve_group(ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS),
        _deps(db_session, user_id=graph.dater_a.id),
    )

    assert dto.id == graph.dater_b.id
    assert dto.chosenName == graph.dater_b.chosen_name
    assert dto.datingProfile is not None
    assert dto.datingProfile.city == City.BOSTON
    # Public shape omits the owner-only fields (ageFrom/interestedGender/etc.).
    assert not hasattr(dto.datingProfile, "ageFrom")


async def test_get_public_profile_missing_returns_none(db_session: AsyncSession) -> None:
    assert await fetch_public_profile(db_session, fake_id()) is None


async def test_public_profile_only_serves_approved_photos(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a has 1 approved + 1 pending photo; a public read drops the pending one,
    # so only the approved photo's media id resolves to a URL.
    bundle = await fetch_public_profile(db_session, graph.dater_a.id)
    assert bundle is not None
    profile, base, photos, prompts = bundle

    # The query already dropped the pending photo (approved-only).
    assert all(photo.approved_at is not None for photo, _ in photos)

    url_by_media = await MediaService(db_session, local_media()).resolve_urls(public_media_ids(profile, photos))
    dto = bundle_to_public_profile(
        profile,
        base,
        photos,
        prompts,
        url_by_media,
        resolve_group(ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS),
        _deps(db_session, user_id=graph.dater_b.id),
    )
    assert dto.datingProfile is not None
    # Exactly the one approved photo is visible, with a resolved URL.
    assert len(dto.datingProfile.photos) == 1
    assert dto.datingProfile.photos[0].approvedAt is not None
    assert dto.datingProfile.photos[0].storageUrl.startswith("http")


async def test_avatar_media_id_resolves_to_url_on_own_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Point the profile's avatar at a READY media; the own-profile read resolves it
    # to its processed (WebP) URL under the viewer's own scope.
    avatar = Media(
        owner_id=graph.dater_a.id,
        file_key=f"{graph.dater_a.id}/a.jpg",
        processed_key=f"{graph.dater_a.id}/a.webp",
        mime_type="image/jpeg",
        file_name="a.jpg",
        state=MediaState.READY,
    )
    db_session.add(avatar)
    await db_session.flush()

    row = await fetch_profile(db_session, graph.dater_a.id)
    assert row is not None
    row.avatar_media_id = avatar.id
    await db_session.flush()

    url_by_media = await MediaService(db_session, local_media()).resolve_urls([avatar.id])
    dto = row_to_profile(
        row, url_by_media, resolve_group(ActionGroupType.PROFILE_ACTIONS), _deps(db_session, user_id=graph.dater_a.id)
    )
    assert dto.avatarUrl is not None
    assert dto.avatarUrl.startswith("http")
    assert avatar.processed_key is not None and avatar.processed_key in dto.avatarUrl


def test_compute_ripeness_matches_hono_formula() -> None:
    # Empty profile -> 0; full profile (6 approved photos, 3 prompts, bio,
    # interests, city) -> 100. Mirrors the TS weighting 30/25/20/15/10.
    assert compute_ripeness([], [], None, [], None) == 0

    photo = MagicMock(approvedAt="2026-01-01T00:00:00Z")
    prompt = MagicMock()
    full = compute_ripeness([photo] * 6, [prompt] * 3, "bio", ["Travel"], City.BOSTON)
    assert full == 100


# ── Actions: happy path ─────────────────────────────────────────────────────────


async def test_update_profile_mutates_row(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = UpdateProfileData(chosenName="Renamed", pushToken="ExpoToken123")

    assert UpdateProfile.is_available(graph.dater_a, deps.user, deps) is True
    result = await UpdateProfile.execute(graph.dater_a, data, db_session, deps.user, deps)

    assert result.message == "Profile updated"
    refreshed = await fetch_profile(db_session, graph.dater_a.id)
    assert refreshed is not None
    assert refreshed.chosen_name == "Renamed"
    assert refreshed.push_token == "ExpoToken123"
    # Unset fields are left untouched (PATCH semantics).
    assert data.avatarMediaId is UNSET


async def test_update_profile_sets_avatar_media_id(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The avatar update sets the FK to a platform Media the caller owns.
    avatar = Media(
        owner_id=graph.dater_a.id,
        file_key=f"{graph.dater_a.id}/av.jpg",
        mime_type="image/jpeg",
        file_name="av.jpg",
    )
    db_session.add(avatar)
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = UpdateProfileData(avatarMediaId=avatar.id)
    await UpdateProfile.execute(graph.dater_a, data, db_session, deps.user, deps)

    refreshed = await fetch_profile(db_session, graph.dater_a.id)
    assert refreshed is not None
    assert refreshed.avatar_media_id == avatar.id


async def test_update_dating_profile_mutates_row(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    dp = graph.dating_profile_a
    data = UpdateDatingProfileData(
        bio="Updated bio",
        datingStatus=DatingStatus.WINGING,
        interests=[Interest.ART, Interest.MUSIC],
    )

    assert UpdateDatingProfile.is_available(dp, deps.user, deps) is True
    result = await UpdateDatingProfile.execute(dp, data, db_session, deps.user, deps)

    assert result.message == "Dating profile updated"
    base = await fetch_dating_profile_base(db_session, graph.dater_a.id)
    assert base is not None
    assert base.bio == "Updated bio"
    assert base.dating_status == DatingStatus.WINGING
    assert base.interests == [Interest.ART, Interest.MUSIC]


async def test_create_dating_profile_inserts(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c has a dating profile in the graph; create one for a fresh profile.
    new_profile = ProfileModel(chosen_name="Fresh", role=UserRole.DATER, gender=Gender.FEMALE)
    db_session.add(new_profile)
    await db_session.flush()

    deps = _deps(db_session, user_id=new_profile.id)
    data = CreateDatingProfileData(
        city=City.NEW_YORK,
        ageFrom=25,
        interestedGender=[Gender.MALE],
        religion=Religion.AGNOSTIC,
        interests=[Interest.BOOKS],
        bio="Hello",
    )

    result = await CreateDatingProfile.execute(data, db_session, deps.user, deps)
    assert result.created_id is not None

    base = await fetch_dating_profile_base(db_session, new_profile.id)
    assert base is not None
    assert base.id == result.created_id
    assert base.city == City.NEW_YORK
    assert base.age_from == 25
    assert base.bio == "Hello"
    # datingStatus defaults to 'open' when omitted.
    assert base.dating_status == DatingStatus.OPEN


# ── Actions: gate denials ───────────────────────────────────────────────────────


async def test_update_profile_denied_for_other_user(graph: DomainGraph, db_session: AsyncSession) -> None:
    # winger trying to edit dater_a's profile row -> is_available is False, which
    # the action router surfaces as PermissionDenied before execute runs.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert UpdateProfile.is_available(graph.dater_a, deps.user, deps) is False


async def test_update_dating_profile_denied_for_other_user(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert UpdateDatingProfile.is_available(graph.dating_profile_a, deps.user, deps) is False


async def test_create_dating_profile_conflict(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a already has a dating profile -> 409.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreateDatingProfileData(
        city=City.BOSTON,
        ageFrom=30,
        interestedGender=[Gender.FEMALE],
        religion=Religion.AGNOSTIC,
        interests=[Interest.FOOD],
    )
    with pytest.raises(DatingProfileAlreadyExistsError):
        await CreateDatingProfile.execute(data, db_session, deps.user, deps)
