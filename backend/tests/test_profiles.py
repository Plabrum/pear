"""Tests for the ported `profiles` domain.

The original Hono domain shipped no `*.test.ts`, so these are authored fresh to
cover the contract the port must preserve:

  * Reads (the GET handlers' query+transformer path):
      - `fetch_profile` / `row_to_profile`              -> /profiles/me
      - `fetch_own_dating_profile` / `dating_profile_to_own` (photos + prompts +
         response threads + ripeness)                   -> /dating-profiles/me
      - `fetch_public_profile` / `bundle_to_public_profile` -> /profiles/{userId}
  * Gated actions (writes):
      - happy path: UpdateProfile / UpdateDatingProfile mutate the row;
        CreateDatingProfile inserts one.
      - gate denial: UpdateProfile.is_available is False for someone else's row;
        CreateDatingProfile raises 409 when a profile already exists.

Reads run against the seeded `graph` under the system-mode `db_session` (RLS is
covered separately by tests/test_rls.py). Actions are driven directly with a
hand-built `ActionDeps` against `db_session`, mirroring tests/test_actions.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from msgspec import UNSET
from sqlalchemy.ext.asyncio import AsyncSession

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
    row_to_profile,
)
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph

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


# ── Reads ──────────────────────────────────────────────────────────────────────


async def test_get_own_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    row = await fetch_profile(db_session, graph.dater_a.id)
    assert row is not None
    dto = row_to_profile(row)

    assert dto.id == graph.dater_a.id
    assert dto.chosenName == graph.dater_a.chosen_name
    assert dto.role == UserRole.DATER
    # gender serializes by .value through msgspec -> matches the Zod enum wire form.
    assert dto.gender is Gender.MALE


async def test_get_own_dating_profile_bundle(graph: DomainGraph, db_session: AsyncSession) -> None:
    bundle = await fetch_own_dating_profile(db_session, graph.dater_a.id)
    assert bundle is not None
    base, photos, prompts = bundle
    dto = dating_profile_to_own(base, photos, prompts)

    assert dto.userId == graph.dater_a.id
    assert dto.city == City.BOSTON
    assert dto.datingStatus == DatingStatus.OPEN
    # graph seeds 1 approved + 1 pending photo, ordered by display_order.
    assert len(dto.photos) == 2
    assert [p.displayOrder for p in dto.photos] == [0, 1]
    approved, pending = dto.photos
    assert approved.approvedAt is not None and approved.suggester is None
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


async def test_get_own_dating_profile_returns_none_when_absent(db_session: AsyncSession) -> None:
    assert await fetch_own_dating_profile(db_session, uuid4()) is None


async def test_get_public_profile(graph: DomainGraph, db_session: AsyncSession) -> None:
    bundle = await fetch_public_profile(db_session, graph.dater_b.id)
    assert bundle is not None
    profile, base, photos, prompts = bundle
    dto = bundle_to_public_profile(profile, base, photos, prompts)

    assert dto.id == graph.dater_b.id
    assert dto.chosenName == graph.dater_b.chosen_name
    assert dto.datingProfile is not None
    assert dto.datingProfile.city == City.BOSTON
    # Public shape omits the owner-only fields (ageFrom/interestedGender/etc.).
    assert not hasattr(dto.datingProfile, "ageFrom")


async def test_get_public_profile_missing_returns_none(db_session: AsyncSession) -> None:
    assert await fetch_public_profile(db_session, uuid4()) is None


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

    assert UpdateProfile.is_available(graph.dater_a, deps) is True
    result = await UpdateProfile.execute(graph.dater_a, data, db_session, deps)

    assert result.message == "Profile updated"
    refreshed = await fetch_profile(db_session, graph.dater_a.id)
    assert refreshed is not None
    assert refreshed.chosen_name == "Renamed"
    assert refreshed.push_token == "ExpoToken123"
    # Unset fields are left untouched (PATCH semantics).
    assert data.avatarUrl is UNSET


async def test_update_dating_profile_mutates_row(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    dp = graph.dating_profile_a
    data = UpdateDatingProfileData(
        bio="Updated bio",
        datingStatus=DatingStatus.WINGING,
        interests=[Interest.ART, Interest.MUSIC],
    )

    assert UpdateDatingProfile.is_available(dp, deps) is True
    result = await UpdateDatingProfile.execute(dp, data, db_session, deps)

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

    result = await CreateDatingProfile.execute(data, db_session, deps)
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
    assert UpdateProfile.is_available(graph.dater_a, deps) is False


async def test_update_dating_profile_denied_for_other_user(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert UpdateDatingProfile.is_available(graph.dating_profile_a, deps) is False


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
        await CreateDatingProfile.execute(data, db_session, deps)
