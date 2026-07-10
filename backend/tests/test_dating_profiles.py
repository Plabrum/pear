from __future__ import annotations

from datetime import date
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.actions import (
    DatingProfileActionKey,
    DeclineForDater,
    Like,
    Pass,
    Report,
    Suggest,
    dating_profile_swipe_actions,
)
from app.domain.dating_profiles.enums import City, DatingStatus
from app.domain.dating_profiles.exceptions import CannotSuggestSelfError
from app.domain.dating_profiles.queries import (
    fetch_likes_you_count,
    fetch_swipe_pool,
    is_active_wingperson,
)
from app.domain.dating_profiles.schemas import DeclineForDaterData, ReportActionData, SuggestActionData
from app.domain.dating_profiles.transformers import row_to_swipe_profile
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.domain.decisions.queries import find_mutual_match, insert_wing_suggestion
from app.domain.photos.enums import PhotoApprovalState
from app.domain.profiles.enums import Gender, UserRole
from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.models import PromptTemplate
from app.domain.reports.models import ProfileReport
from app.platform.actions.base import ActionGroup, EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.schemas import ActionDTO
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.factories import (
    MediaFactory,
    ProfileFactory,
    ProfilePhotoFactory,
    ProfilePromptFactory,
    PromptResponseFactory,
)
from tests.fixtures.graph import DomainGraph
from tests.fixtures.media import local_media

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor.

    `push` is an AsyncMock so the (stub) match/suggestion pushes can be asserted.
    """
    push = MagicMock()
    push.send = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


def _push(deps: ActionDeps) -> AsyncMock:
    return cast(AsyncMock, deps.push.send)


def _swipe_group() -> ActionGroup:
    """The swipe action group (importing actions.py has registered it)."""
    return dating_profile_swipe_actions


def _action_keys(dtos: list[ActionDTO]) -> set[str]:
    """The bare action_key suffixes of a hydrated `actions` list.

    Each `ActionDTO.action` is `dating_profile_swipe_actions__<key>`; strip the
    `{group}__` prefix to compare against `DatingProfileActionKey` values.
    """
    return {dto.action.split("__", 1)[1] for dto in dtos}


async def _normalize_ages(graph: DomainGraph, db_session: AsyncSession) -> None:
    """Pin candidate DOBs (~30) and widen dater_a's preferred range to [18, 99].

    Makes age-filter membership deterministic regardless of the faker-advanced seed
    ages, so a test asserting on dater_b/dater_c isn't order-dependent.
    """
    in_range = date(1995, 1, 1)
    graph.dater_b.date_of_birth = in_range
    graph.dater_c.date_of_birth = in_range
    graph.dating_profile_a.age_from = 18
    graph.dating_profile_a.age_to = 99
    await db_session.flush()


# ── the collapsed swipe read ─────────────────────────────────────────────────


async def test_swipe_pool_returns_preference_matches(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}

    # dater_b and dater_c match dater_a's prefs (Boston, open, female, in range).
    assert graph.dater_b.id in user_ids
    assert graph.dater_c.id in user_ids
    # Never include self.
    assert graph.dater_a.id not in user_ids


async def test_swipe_pool_excludes_when_candidate_not_interested(graph: DomainGraph, db_session: AsyncSession) -> None:
    """Matching is bidirectional: a candidate uninterested in the viewer's gender is
    filtered out even though the viewer wants the candidate's gender."""
    await _normalize_ages(graph, db_session)
    # dater_a is MALE. Narrow dater_b to women-only so dater_b is NOT open to dater_a.
    graph.dating_profile_b.interested_gender = [Gender.FEMALE]
    await db_session.flush()

    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}

    # dater_b excluded by the reverse-direction filter; dater_c (still open to men) stays.
    assert graph.dater_b.id not in user_ids
    assert graph.dater_c.id in user_ids


async def test_swipe_pool_orders_suggestions_first(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    # The graph seeds a pending winger suggestion (dater_a -> dater_b). It must sort
    # ahead of the un-suggested dater_c, with its note + suggester surfaced.
    first = rows[0]
    assert first.user_id == graph.dater_b.id
    assert len(first.suggestions) == 1
    assert first.suggestions[0].winger_id == graph.winger.id
    assert first.suggestions[0].winger_name == graph.winger.chosen_name
    assert first.suggestions[0].note == graph.suggestion.note


async def test_swipe_row_maps_to_camel_case(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    suggested = next(r for r in rows if r.user_id == graph.dater_b.id)
    deps = _deps(db_session, user_id=graph.dater_a.id)
    dto = await row_to_swipe_profile(suggested, local_media(), _swipe_group(), deps)

    assert dto.profileId == graph.dating_profile_b.id
    assert dto.userId == graph.dater_b.id
    assert dto.chosenName == graph.dater_b.chosen_name
    assert dto.city == City.BOSTON
    assert dto.datingStatus == DatingStatus.OPEN
    assert dto.gender is Gender.FEMALE
    assert len(dto.suggestions) == 1
    assert dto.suggestions[0].wingerId == graph.winger.id
    assert dto.suggestions[0].wingerName == graph.winger.chosen_name
    assert dto.suggestions[0].note == graph.suggestion.note


async def test_swipe_pool_surfaces_photo_pick_and_approved_prompt_response(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    """A winger-suggested APPROVED photo on the candidate surfaces `pickedByName`;
    a self-uploaded photo doesn't. An APPROVED prompt response surfaces in
    `responses`; a PENDING one on the same prompt is excluded."""
    await _normalize_ages(graph, db_session)

    self_media = await MediaFactory.create_async(db_session, owner_id=graph.dater_b.id)
    picked_media = await MediaFactory.create_async(db_session, owner_id=graph.dater_b.id)
    await ProfilePhotoFactory.create_async(
        db_session,
        dating_profile_id=graph.dating_profile_b.id,
        owner_id=graph.dater_b.id,
        media_id=self_media.id,
        display_order=0,
        state=PhotoApprovalState.APPROVED,
    )
    await ProfilePhotoFactory.create_async(
        db_session,
        dating_profile_id=graph.dating_profile_b.id,
        owner_id=graph.dater_b.id,
        suggester_id=graph.winger.id,
        media_id=picked_media.id,
        display_order=1,
        state=PhotoApprovalState.APPROVED,
    )

    template = (await db_session.execute(select(PromptTemplate).limit(1))).scalar_one()
    profile_prompt = await ProfilePromptFactory.create_async(
        db_session,
        dating_profile_id=graph.dating_profile_b.id,
        owner_id=graph.dater_b.id,
        prompt_template_id=template.id,
    )
    await PromptResponseFactory.create_async(
        db_session,
        user_id=graph.winger.id,
        profile_owner_id=graph.dater_b.id,
        profile_prompt_id=profile_prompt.id,
        message="Approved comment",
        state=ApprovalState.APPROVED,
    )
    await PromptResponseFactory.create_async(
        db_session,
        user_id=graph.winger.id,
        profile_owner_id=graph.dater_b.id,
        profile_prompt_id=profile_prompt.id,
        message="Still pending comment",
        state=ApprovalState.PENDING,
    )

    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    candidate = next(r for r in rows if r.user_id == graph.dater_b.id)

    photos_by_key = {p.key: p.picked_by_name for p in candidate.photos}
    assert len(candidate.photos) == 2
    self_key = next(key for key, picked_by in photos_by_key.items() if picked_by is None)
    picked_key = next(key for key, picked_by in photos_by_key.items() if picked_by is not None)
    assert photos_by_key[picked_key] == graph.winger.chosen_name
    assert photos_by_key[self_key] is None

    assert len(candidate.prompts) == 1
    prompt = candidate.prompts[0]
    assert prompt.question == template.question
    assert prompt.answer == profile_prompt.answer
    assert len(prompt.responses) == 1
    assert prompt.responses[0].message == "Approved comment"
    assert prompt.responses[0].winger_name == graph.winger.chosen_name


async def test_swipe_pool_surfaces_multiple_wingers_suggesting_same_candidate(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    """Two different active wingers each suggesting dater_c to dater_a must both
    surface — the `unique_actor_recipient_suggestion` partial index allows one row
    per (dater, recipient, winger), not one row per (dater, recipient)."""
    await _normalize_ages(graph, db_session)

    second_winger = await ProfileFactory.create_async(db_session, state=UserRole.WINGER, gender=Gender.NON_BINARY)
    db_session.add(
        Contact(
            user_id=graph.dater_a.id,
            phone_number=second_winger.phone_number or "+15555550099",
            winger_id=second_winger.id,
            state=WingpersonStatus.ACTIVE,
        )
    )
    await db_session.flush()

    inserted_first = await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, graph.winger.id, "You'd love them", DecisionState.PENDING
    )
    inserted_second = await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, second_winger.id, None, DecisionState.PENDING
    )
    assert inserted_first is True
    assert inserted_second is True

    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    candidate = next(r for r in rows if r.user_id == graph.dater_c.id)

    winger_ids = {s.winger_id for s in candidate.suggestions}
    assert winger_ids == {graph.winger.id, second_winger.id}
    notes = {s.winger_id: s.note for s in candidate.suggestions}
    assert notes[graph.winger.id] == "You'd love them"
    assert notes[second_winger.id] is None


async def test_insert_wing_suggestion_rejects_already_decided_pair(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    """A stale cached pool page (or a race with the dater's own swipe) could still
    reach `insert_wing_suggestion` for a pair the dater already has a REAL
    (non-suggested) decision on. The `WHERE NOT EXISTS` guard must reject the
    insert even though the conflict target only covers `suggested_by IS NOT NULL`
    rows and wouldn't otherwise collide with a real decision row."""
    db_session.add(Decision(actor_id=graph.dater_a.id, recipient_id=graph.dater_c.id, state=DecisionState.APPROVED))
    await db_session.flush()

    inserted = await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, graph.winger.id, None, DecisionState.PENDING
    )
    assert inserted is False

    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_c.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].suggested_by is None
    assert rows[0].state == DecisionState.APPROVED


async def test_like_resolves_every_pending_suggestion_for_the_pair(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    """A dater's own swipe must resolve ALL wingers' pending suggestions for that
    recipient, not just the first one found — `apply_dater_decision` used to
    `.scalar_one_or_none()` a single row, which would now raise once multiple
    wingers can each suggest the same candidate."""
    second_winger = await ProfileFactory.create_async(db_session, state=UserRole.WINGER, gender=Gender.NON_BINARY)
    db_session.add(
        Contact(
            user_id=graph.dater_a.id,
            phone_number=second_winger.phone_number or "+15555550098",
            winger_id=second_winger.id,
            state=WingpersonStatus.ACTIVE,
        )
    )
    await db_session.flush()

    await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, graph.winger.id, None, DecisionState.PENDING
    )
    await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, second_winger.id, None, DecisionState.PENDING
    )

    deps = _deps(db_session, user_id=graph.dater_a.id)
    await Like.execute(graph.dating_profile_c, EmptyActionData(), db_session, deps.user, deps)

    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_c.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    assert {row.state for row in rows} == {DecisionState.APPROVED}
    assert {row.suggested_by for row in rows} == {graph.winger.id, second_winger.id}


async def test_like_resolves_pending_suggestions_and_leaves_declined_rows_alone(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    """`DeclinedState` is terminal, so a sibling winger's already-DECLINED row must
    not raise `InvalidTransitionError` when the dater likes the candidate — it
    used to call `sm_service.transition(...)` unconditionally for every
    non-matching row, which crashed a normal Like whenever one winger's
    suggestion was DECLINED and another's was still PENDING for the same pair."""
    second_winger = await ProfileFactory.create_async(db_session, state=UserRole.WINGER, gender=Gender.NON_BINARY)
    db_session.add(
        Contact(
            user_id=graph.dater_a.id,
            phone_number=second_winger.phone_number or "+15555550099",
            winger_id=second_winger.id,
            state=WingpersonStatus.ACTIVE,
        )
    )
    await db_session.flush()

    await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, graph.winger.id, None, DecisionState.PENDING
    )
    await insert_wing_suggestion(
        db_session, graph.dater_a.id, graph.dater_c.id, second_winger.id, None, DecisionState.DECLINED
    )

    deps = _deps(db_session, user_id=graph.dater_a.id)
    # Must not raise even though second_winger's row is already DECLINED (terminal).
    await Like.execute(graph.dating_profile_c, EmptyActionData(), db_session, deps.user, deps)

    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_c.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 2
    by_winger = {row.suggested_by: row.state for row in rows}
    assert by_winger[graph.winger.id] == DecisionState.APPROVED
    assert by_winger[second_winger.id] == DecisionState.DECLINED


# ── action hydration on the swipe read ───────────────────────────────────────


async def test_swipe_row_hydrates_dater_actions(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A dater viewing a candidate (other profile) sees the dater gestures: like,
    # pass, report. The winger-only gestures (suggest, decline) are role-gated off.
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    candidate = next(r for r in rows if r.user_id == graph.dater_b.id)
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)
    dto = await row_to_swipe_profile(candidate, local_media(), _swipe_group(), deps)

    assert _action_keys(dto.actions) == {
        DatingProfileActionKey.LIKE,
        DatingProfileActionKey.PASS,
        DatingProfileActionKey.REPORT,
    }
    # Every hydrated action belongs to this group and is available (not disabled).
    for a in dto.actions:
        assert a.action_group_type == ActionGroupType.DATING_PROFILE_SWIPE_ACTIONS
        assert a.available is True
        assert a.disabled_reason is None


async def test_swipe_row_hydrates_winger_actions(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A winger swiping their dater's pool (daterId context) sees the winger gestures:
    # suggest, decline, report. The dater gestures (like, pass) are role-gated off.
    # Active-wingperson is enforced by RLS at execute, NOT in is_available, so the
    # winger sees suggest/decline regardless.
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(
        db_session,
        viewer_id=graph.winger.id,
        page_size=20,
        page_offset=0,
        filter_dater_id=graph.dater_a.id,
    )
    candidate = next(r for r in rows if r.user_id == graph.dater_b.id)
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    dto = await row_to_swipe_profile(candidate, local_media(), _swipe_group(), deps)

    assert _action_keys(dto.actions) == {
        DatingProfileActionKey.SUGGEST,
        DatingProfileActionKey.DECLINE,
        DatingProfileActionKey.REPORT,
    }


async def test_swipe_route_hydrates_actions(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The route loop resolves the group once and hydrates every row. Mirror it: every
    # returned card carries the dater gestures, gated against the per-row scalar stub.
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    group = _swipe_group()
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)
    dtos = [await row_to_swipe_profile(r, local_media(), group, deps) for r in rows]

    assert dtos  # the dater has a non-empty pool
    for dto in dtos:
        assert _action_keys(dto.actions) == {
            DatingProfileActionKey.LIKE,
            DatingProfileActionKey.PASS,
            DatingProfileActionKey.REPORT,
        }


async def test_swipe_pool_excludes_already_decided(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_a passes on dater_c (a NOT-NULL decision) -> dater_c drops out.
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            state=DecisionState.DECLINED,
        )
    )
    await db_session.flush()

    rows = await fetch_swipe_pool(db_session, viewer_id=graph.dater_a.id, page_size=20, page_offset=0)
    user_ids = {r.user_id for r in rows}
    assert graph.dater_c.id not in user_ids
    # dater_b (only a NULL suggestion against it, not a real decision) stays.
    assert graph.dater_b.id in user_ids


async def test_swipe_pool_winger_only_keeps_suggested(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(
        db_session,
        viewer_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
        winger_only=True,
    )
    # Only the pending-suggestion card (dater_b) survives the wingerOnly EXISTS.
    assert {r.user_id for r in rows} == {graph.dater_b.id}


async def test_swipe_pool_likes_you_only_excludes_matched(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    # dater_b approved dater_a in the graph, but they are already matched -> excluded.
    # dater_c approves dater_a fresh (no match) -> dater_c surfaces. The count agrees.
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            state=DecisionState.APPROVED,
        )
    )
    await db_session.flush()

    rows = await fetch_swipe_pool(
        db_session,
        viewer_id=graph.dater_a.id,
        page_size=20,
        page_offset=0,
        likes_you_only=True,
    )
    user_ids = {r.user_id for r in rows}
    assert graph.dater_c.id in user_ids
    assert graph.dater_b.id not in user_ids  # already matched
    assert await fetch_likes_you_count(db_session, graph.dater_a.id) == 1


async def test_swipe_pool_winger_context_dater_scoped(graph: DomainGraph, db_session: AsyncSession) -> None:
    await _normalize_ages(graph, db_session)
    rows = await fetch_swipe_pool(
        db_session,
        viewer_id=graph.winger.id,
        page_size=20,
        page_offset=0,
        filter_dater_id=graph.dater_a.id,
    )
    user_ids = {r.user_id for r in rows}
    # Candidates matching dater_a's prefs, minus the dater and the winger.
    assert graph.dater_b.id in user_ids
    assert graph.dater_c.id in user_ids
    assert graph.dater_a.id not in user_ids
    assert graph.winger.id not in user_ids


async def test_is_active_wingperson_gate(graph: DomainGraph, db_session: AsyncSession) -> None:
    assert await is_active_wingperson(db_session, graph.winger.id, graph.dater_a.id) is True
    # dater_c has no contact with the winger -> the route would raise 403.
    assert await is_active_wingperson(db_session, graph.winger.id, graph.dater_c.id) is False


# ── Like / Pass actions ──────────────────────────────────────────────────────


async def test_like_no_match(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a likes dater_c's dating profile. dater_c has not approved back -> no match.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    result = await Like.execute(graph.dating_profile_c, EmptyActionData(), db_session, deps.user, deps)
    assert result.created_id is None
    assert await find_mutual_match(db_session, graph.dater_a.id, graph.dater_c.id) is None

    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert row.state == DecisionState.APPROVED
    _push(deps).assert_not_called()


async def test_like_creates_match_on_mutual(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed dater_c -> dater_a as an existing approval, then dater_a likes dater_c
    # back: the second approval makes the pair mutual. The Like forms the match row
    # in-request (guarded INSERT, gated by the matches_insert RLS floor) and returns
    # the REAL match id as `created_id`.
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            state=DecisionState.APPROVED,
        )
    )
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    result = await Like.execute(graph.dating_profile_c, EmptyActionData(), db_session, deps.user, deps)

    # `created_id` is the real, navigable match id for the freshly-formed pair.
    match = await find_mutual_match(db_session, graph.dater_a.id, graph.dater_c.id)
    assert match is not None
    assert result.created_id == match.id


async def test_like_lands_on_pending_winger_suggestion(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds a pending winger suggestion (actor=dater_a, recipient=dater_b,
    # decision IS NULL, suggested_by=winger). dater_a liking dater_b's profile must
    # UPDATE that same row (preserving suggested_by) — not create a second row — and
    # form a match because dater_b already approved dater_a.
    deps = _deps(db_session, user_id=graph.dater_a.id)
    result = await Like.execute(graph.dating_profile_b, EmptyActionData(), db_session, deps.user, deps)

    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_b.id,
                )
            )
        )
        .scalars()
        .all()
    )
    # Still exactly one row (the winger's pending suggestion), now finalised.
    assert len(rows) == 1
    assert rows[0].state == DecisionState.APPROVED
    assert rows[0].suggested_by == graph.winger.id  # provenance preserved
    # The match for this pair exists (the graph seeds it). The like finalising the
    # pending row doesn't double-create it, so created_id stays None.
    assert result.created_id is None
    match = await find_mutual_match(db_session, graph.dater_a.id, graph.dater_b.id)
    assert match is not None


async def test_pass_upserts_declined(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    await Pass.execute(graph.dating_profile_c, EmptyActionData(), db_session, deps.user, deps)
    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert row.state == DecisionState.DECLINED


async def test_like_role_gate_denies_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A winger may not Like — is_available gates the swipe to daters.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert Like.is_available(graph.dating_profile_c, deps.user, deps) is False


async def test_like_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert Like.is_available(graph.dating_profile_a, deps.user, deps) is False


# ── Suggest action ───────────────────────────────────────────────────────────


async def test_suggest_happy(graph: DomainGraph, db_session: AsyncSession) -> None:
    # winger (active for dater_a) suggests dater_c's profile to dater_a, with a note.
    graph.dater_a.push_token = "ExpoTokenA"
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert Suggest.is_available(graph.dating_profile_c, deps.user, deps) is True

    data = SuggestActionData(daterId=graph.dater_a.id, note="You two!")
    result = await Suggest.execute(graph.dating_profile_c, data, db_session, deps.user, deps)
    assert result.message == "Suggestion created"

    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert row.suggested_by == graph.winger.id
    assert row.state is DecisionState.PENDING  # the dater must act
    assert row.note == "You two!"
    # A new pending suggestion -> the dater gets a push.
    _push(deps).assert_awaited_once()
    call = _push(deps).await_args
    assert call is not None
    assert call.args[0] == "ExpoTokenA"


async def test_suggest_duplicate_is_noop_no_push(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A second suggestion on a pair that already has a decision row is a no-op
    # conflict: insert_wing_suggestion's ON CONFLICT DO NOTHING writes nothing and
    # returns False, so no duplicate row is created and the dater gets NO push.
    graph.dater_a.push_token = "ExpoTokenA"
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = SuggestActionData(daterId=graph.dater_a.id, note="You two!")

    await Suggest.execute(graph.dating_profile_c, data, db_session, deps.user, deps)
    _push(deps).assert_awaited_once()  # first suggestion pushes
    _push(deps).reset_mock()

    # Second, conflicting suggestion on the same (dater_a -> dater_c) pair.
    again = SuggestActionData(daterId=graph.dater_a.id, note="Again!")
    await Suggest.execute(graph.dating_profile_c, again, db_session, deps.user, deps)

    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_c.id,
                )
            )
        )
        .scalars()
        .all()
    )
    # Exactly one row, with the ORIGINAL note (DO NOTHING never overwrote it).
    assert len(rows) == 1
    assert rows[0].note == "You two!"
    # The conflicting suggestion fired no push.
    _push(deps).assert_not_awaited()


# The "non-active wingperson is denied" case is enforced by the decisions INSERT
# RLS policy (see tests/test_rls.py::test_winger_cannot_insert_decision_for_unrelated_dater)
# and the action dispatcher translates that DB denial into a 403
# (tests/test_actions.py::test_trigger_translates_rls_denial_to_403).


async def test_suggest_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Suggesting the dater their own profile (recipient == daterId) -> 400.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = SuggestActionData(daterId=graph.dater_a.id)
    with pytest.raises(CannotSuggestSelfError):
        await Suggest.execute(graph.dating_profile_a, data, db_session, deps.user, deps)


async def test_suggest_role_gate_denies_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)
    assert Suggest.is_available(graph.dating_profile_c, deps.user, deps) is False


# ── DeclineForDater action ─────────────────────────────────────────────────────


async def test_decline_for_dater_writes_declined_and_no_push(graph: DomainGraph, db_session: AsyncSession) -> None:
    # winger (active for dater_a) declines dater_c's profile on dater_a's behalf:
    # writes a 'declined' decision so it leaves the pool, and never pushes the dater.
    graph.dater_a.push_token = "ExpoTokenA"
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeclineForDater.is_available(graph.dating_profile_c, deps.user, deps) is True

    data = DeclineForDaterData(daterId=graph.dater_a.id)
    result = await DeclineForDater.execute(graph.dating_profile_c, data, db_session, deps.user, deps)
    assert result.message == "Declined"

    row = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert row.state == DecisionState.DECLINED
    assert row.suggested_by == graph.winger.id  # winger-authored, on the dater's behalf
    # A decline is terminal for the dater — never pings them.
    _push(deps).assert_not_awaited()


async def test_decline_for_dater_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Declining the dater's own profile (recipient == daterId) -> 400.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = DeclineForDaterData(daterId=graph.dater_a.id)
    with pytest.raises(CannotSuggestSelfError):
        await DeclineForDater.execute(graph.dating_profile_a, data, db_session, deps.user, deps)


async def test_decline_for_dater_role_gate_denies_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)
    assert DeclineForDater.is_available(graph.dating_profile_c, deps.user, deps) is False


# ── Report action ────────────────────────────────────────────────────────────


async def test_report_inserts_report_and_declines(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a reports dater_c's profile (no prior decision between them).
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert Report.is_available(graph.dating_profile_c, deps.user, deps) is True

    data = ReportActionData(reason="Inappropriate photos")
    result = await Report.execute(graph.dating_profile_c, data, db_session, deps.user, deps)
    assert result.message == "Report filed"
    assert "/decisions" in result.invalidate_queries

    report = (
        await db_session.execute(
            select(ProfileReport).where(
                ProfileReport.reporter_id == graph.dater_a.id,
                ProfileReport.reported_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert report.reason == "Inappropriate photos"

    # A declined decision was upserted so the reported profile leaves the queue.
    decision = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert decision.state == DecisionState.DECLINED


async def test_report_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert Report.is_available(graph.dating_profile_a, deps.user, deps) is False
