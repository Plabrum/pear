from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.profiles.enums import Gender, UserRole
from app.domain.profiles.models import Profile as ProfileModel
from app.domain.prompts.actions import (
    ApprovePromptResponse,
    CreateProfilePrompt,
    CreatePromptResponse,
    DeleteProfilePrompt,
    DeletePromptResponse,
)
from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.exceptions import (
    DatingProfileNotFoundError,
    NotWingpersonOrMatchError,
    ProfilePromptNotFoundError,
)
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate
from app.domain.prompts.queries import (
    AuthoredResponseRow,
    fetch_authored_prompt_responses,
    fetch_onboarding_prompt_templates,
    fetch_own_profile_prompts,
    fetch_prompt_templates,
)
from app.domain.prompts.schemas import (
    CreateProfilePromptData,
    CreatePromptResponseData,
)
from app.domain.prompts.transformers import (
    authored_response_to_dto,
    row_to_profile_prompt,
    row_to_prompt_template,
)
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import resolve_group
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.models import StateTransitionLog
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph
from tests.fixtures.ids import fake_id

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


async def test_list_prompt_templates(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_prompt_templates(db_session)
    assert len(rows) > 0
    dtos = [row_to_prompt_template(r) for r in rows]
    # Ordered ascending by question text.
    questions = [d.question for d in dtos]
    assert questions == sorted(questions)
    assert all(d.id is not None and d.question for d in dtos)


async def test_onboarding_prompt_templates_limit(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_onboarding_prompt_templates(db_session, 5)
    assert 1 <= len(rows) <= 5


def _profile_prompt_dtos(bundles, deps: ActionDeps):
    """Hydrate the prompt bundle into DTOs under a given actor (for action gating).

    The winger author has no avatar, so an empty resolved-URL map is correct.
    """
    prompt_group = resolve_group(ActionGroupType.PROFILE_PROMPT_ACTIONS)
    response_group = resolve_group(ActionGroupType.PROMPT_RESPONSE_ACTIONS)
    return [row_to_profile_prompt(p, q, r, {}, prompt_group, response_group, deps) for p, q, r in bundles]


async def test_get_own_profile_prompts_bundle(graph: DomainGraph, db_session: AsyncSession) -> None:
    bundles = await fetch_own_profile_prompts(db_session, graph.dater_a.id)
    deps = _deps(db_session, user_id=graph.dater_a.id)
    dtos = _profile_prompt_dtos(bundles, deps)

    # graph seeds 1 prompt with 1 (pending) response carrying its winger author.
    assert len(dtos) == 1
    prompt = dtos[0]
    assert prompt.datingProfileId == graph.dating_profile_a.id
    assert prompt.template.question  # joined template text present
    assert len(prompt.responses) == 1
    resp = prompt.responses[0]
    assert resp.status is ApprovalState.PENDING
    assert resp.author is not None and resp.author.id == graph.winger.id
    assert resp.author.chosenName == graph.winger.chosen_name


# ── Reads: hydrated `actions` field (gating projected onto the read contract) ─────


async def test_own_profile_prompts_actions_for_owner_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The owning dater sees [delete] on their prompt; on the pending winger response
    # they own the profile of, both [approve, delete].
    bundles = await fetch_own_profile_prompts(db_session, graph.dater_a.id)
    deps = _deps(db_session, user_id=graph.dater_a.id)
    prompt = _profile_prompt_dtos(bundles, deps)[0]

    assert [a.action for a in prompt.actions] == ["profile_prompt_actions__delete"]
    assert all(a.action_group_type is ActionGroupType.PROFILE_PROMPT_ACTIONS for a in prompt.actions)

    resp = prompt.responses[0]
    assert sorted(a.action for a in resp.actions) == [
        "prompt_response_actions__approve",
        "prompt_response_actions__delete",
    ]
    assert all(a.action_group_type is ActionGroupType.PROMPT_RESPONSE_ACTIONS for a in resp.actions)
    # The approve action carries its target state (PENDING -> APPROVED).
    approve = next(a for a in resp.actions if a.action == "prompt_response_actions__approve")
    assert approve.target_state == ApprovalState.APPROVED.value


async def test_own_profile_prompts_response_actions_for_author(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Viewed by the winger who authored the response: they may [delete] their own
    # comment but not approve (only the profile owner approves). The prompt itself
    # offers no actions to a non-owning winger.
    bundles = await fetch_own_profile_prompts(db_session, graph.dater_a.id)
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    prompt = _profile_prompt_dtos(bundles, deps)[0]

    assert prompt.actions == []
    resp = prompt.responses[0]
    assert [a.action for a in resp.actions] == ["prompt_response_actions__delete"]


async def test_own_profile_prompts_response_actions_drop_approve_when_approved(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    # Once approved, the profile owner no longer sees `approve` (gate narrows to
    # pending) but may still delete.
    graph.prompt_response.state = ApprovalState.APPROVED
    await db_session.flush()
    bundles = await fetch_own_profile_prompts(db_session, graph.dater_a.id)
    deps = _deps(db_session, user_id=graph.dater_a.id)
    resp = _profile_prompt_dtos(bundles, deps)[0].responses[0]

    assert [a.action for a in resp.actions] == ["prompt_response_actions__delete"]


async def test_get_own_profile_prompts_empty(db_session: AsyncSession) -> None:
    assert await fetch_own_profile_prompts(db_session, fake_id()) == []


# ── Reads: responses I added (user_id = me) ──────────────────────────────────────


async def test_fetch_authored_prompt_responses(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds one winger-authored response on dater_a's prompt, pending.
    rows = await fetch_authored_prompt_responses(db_session, graph.winger.id, 50)
    assert len(rows) == 1
    row = rows[0]
    assert row.id == graph.prompt_response.id
    assert row.dater_id == graph.dater_a.id
    assert row.dater_name == graph.dater_a.chosen_name
    assert row.message == graph.prompt_response.message
    assert row.state is ApprovalState.PENDING

    dto = authored_response_to_dto(row)
    assert dto.daterId == graph.dater_a.id
    assert dto.promptQuestion  # joined from the template
    assert dto.status == "pending"


async def test_fetch_authored_prompt_responses_scoped_to_author(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A user who authored no responses sees nothing.
    assert await fetch_authored_prompt_responses(db_session, graph.dater_c.id, 50) == []


async def test_authored_prompt_responses_honors_limit(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed a second winger-authored response so the feed has > 1 row.
    db_session.add(
        PromptResponse(
            user_id=graph.winger.id,
            profile_owner_id=graph.dater_a.id,
            profile_prompt_id=graph.profile_prompt.id,
            message="another comment",
            state=ApprovalState.PENDING,
        )
    )
    await db_session.flush()
    assert len(await fetch_authored_prompt_responses(db_session, graph.winger.id, 50)) == 2
    assert len(await fetch_authored_prompt_responses(db_session, graph.winger.id, 1)) == 1


async def test_authored_response_status_matrix(graph: DomainGraph, db_session: AsyncSession) -> None:
    def _row(state: ApprovalState) -> AuthoredResponseRow:
        return AuthoredResponseRow(
            id=graph.prompt_response.id,
            dater_id=graph.dater_a.id,
            dater_name="Dana",
            prompt_question="Q?",
            message="hi",
            state=state,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )

    assert authored_response_to_dto(_row(ApprovalState.REJECTED)).status == "not_accepted"
    assert authored_response_to_dto(_row(ApprovalState.APPROVED)).status == "accepted"
    assert authored_response_to_dto(_row(ApprovalState.PENDING)).status == "pending"


# ── Actions: CreateProfilePrompt ─────────────────────────────────────────────────


async def test_create_profile_prompt_inserts(graph: DomainGraph, db_session: AsyncSession) -> None:
    template = (await db_session.execute(select(PromptTemplate).limit(1))).scalar_one()
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreateProfilePromptData(promptTemplateId=template.id, answer="My answer")

    result = await CreateProfilePrompt.execute(data, db_session, deps.user, deps)
    assert result.created_id is not None

    prompt = (await db_session.execute(select(ProfilePrompt).where(ProfilePrompt.id == result.created_id))).scalar_one()
    assert prompt.answer == "My answer"
    assert prompt.dating_profile_id == graph.dating_profile_a.id


async def test_create_profile_prompt_no_dating_profile(db_session: AsyncSession) -> None:
    # A profile with no dating profile -> 404.
    fresh = ProfileModel(chosen_name="NoDP", state=UserRole.DATER, gender=Gender.FEMALE)
    db_session.add(fresh)
    await db_session.flush()
    template = (await db_session.execute(select(PromptTemplate).limit(1))).scalar_one()

    deps = _deps(db_session, user_id=fresh.id)
    data = CreateProfilePromptData(promptTemplateId=template.id, answer="x")
    with pytest.raises(DatingProfileNotFoundError):
        await CreateProfilePrompt.execute(data, db_session, deps.user, deps)


# ── Actions: DeleteProfilePrompt ─────────────────────────────────────────────────


async def test_delete_profile_prompt_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert DeleteProfilePrompt.is_available(graph.profile_prompt, deps.user, deps) is True

    result = await DeleteProfilePrompt.execute(graph.profile_prompt, EmptyActionData(), db_session, deps.user, deps)
    assert result.message == "Prompt deleted"
    # Soft delete sets `deleted_at`; the production SELECT filter (installed in
    # factory.py) then hides it. The test harness doesn't install that filter, so
    # we assert on the soft-delete marker directly.
    assert graph.profile_prompt.deleted_at is not None


async def test_delete_profile_prompt_denied_for_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A winger is not a dater -> is_available is False (gate denial before execute).
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeleteProfilePrompt.is_available(graph.profile_prompt, deps.user, deps) is False


async def test_delete_profile_prompt_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b is a dater but doesn't own dater_a's prompt. Ownership now lives in
    # is_available (owner_id compare) -> not offered (a request would be 403).
    deps = _deps(db_session, user_id=graph.dater_b.id)
    assert DeleteProfilePrompt.is_available(graph.profile_prompt, deps.user, deps) is False


# ── Actions: CreatePromptResponse ────────────────────────────────────────────────


async def test_create_prompt_response_as_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="self note")

    result = await CreatePromptResponse.execute(data, db_session, deps.user, deps)
    assert result.created_id is not None
    row = (await db_session.execute(select(PromptResponse).where(PromptResponse.id == result.created_id))).scalar_one()
    assert row.user_id == graph.dater_a.id
    assert row.message == "self note"
    assert row.state is ApprovalState.PENDING


async def test_create_prompt_response_as_active_wingperson(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="winger note")

    result = await CreatePromptResponse.execute(data, db_session, deps.user, deps)
    assert result.created_id is not None


async def test_create_prompt_response_as_match(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b is matched with dater_a -> may comment on dater_a's prompt.
    deps = _deps(db_session, user_id=graph.dater_b.id)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="match note")
    result = await CreatePromptResponse.execute(data, db_session, deps.user, deps)
    assert result.created_id is not None


async def test_create_prompt_response_unrelated_403(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c has no contact + no match with dater_a -> 403.
    deps = _deps(db_session, user_id=graph.dater_c.id)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="nope")
    with pytest.raises(NotWingpersonOrMatchError):
        await CreatePromptResponse.execute(data, db_session, deps.user, deps)


async def test_create_prompt_response_missing_prompt_404(db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=fake_id())
    data = CreatePromptResponseData(profilePromptId=fake_id(), message="x")
    with pytest.raises(ProfilePromptNotFoundError):
        await CreatePromptResponse.execute(data, db_session, deps.user, deps)


# ── Actions: ApprovePromptResponse (state machine) ───────────────────────────────


async def test_approve_prompt_response_owner_transitions(graph: DomainGraph, db_session: AsyncSession) -> None:
    response = graph.prompt_response
    deps = _deps(db_session, user_id=graph.dater_a.id)

    assert response.state is ApprovalState.PENDING
    assert ApprovePromptResponse.is_available(response, deps.user, deps) is True

    result = await ApprovePromptResponse.execute(response, EmptyActionData(), db_session, deps.user, deps)
    assert result.message == "Comment approved"

    refreshed = (await db_session.execute(select(PromptResponse).where(PromptResponse.id == response.id))).scalar_one()
    assert refreshed.state is ApprovalState.APPROVED

    # The transition wrote an audit log row (PENDING -> APPROVED).
    logs = (
        (await db_session.execute(select(StateTransitionLog).where(StateTransitionLog.object_id == response.id)))
        .scalars()
        .all()
    )
    assert len(logs) == 1
    assert logs[0].object_type == PromptResponse.__tablename__
    assert logs[0].from_state == ApprovalState.PENDING.value
    assert logs[0].to_state == ApprovalState.APPROVED.value
    assert logs[0].actor_id == graph.dater_a.id


async def test_approve_prompt_response_denied_for_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A winger may never approve -> is_available is False (gate denial).
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert ApprovePromptResponse.is_available(graph.prompt_response, deps.user, deps) is False


async def test_approve_prompt_response_denied_for_non_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b is a dater but doesn't own the prompt's profile. Ownership now lives
    # in is_available (profile_owner_id compare) -> not offered (a request -> 403).
    deps = _deps(db_session, user_id=graph.dater_b.id)
    assert ApprovePromptResponse.is_available(graph.prompt_response, deps.user, deps) is False


async def test_approve_prompt_response_not_available_when_already_approved(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    graph.prompt_response.state = ApprovalState.APPROVED
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.dater_a.id)
    # Already approved -> not pending -> is_available is False.
    assert ApprovePromptResponse.is_available(graph.prompt_response, deps.user, deps) is False


# ── Actions: DeletePromptResponse ────────────────────────────────────────────────


async def test_delete_prompt_response_as_author(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger authored the seeded response -> may delete it.
    response = graph.prompt_response
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeletePromptResponse.is_available(response, deps.user, deps) is True

    result = await DeletePromptResponse.execute(response, EmptyActionData(), db_session, deps.user, deps)
    assert result.message == "Comment deleted"
    # Soft delete sets `deleted_at` (the production SELECT filter then hides it).
    assert response.deleted_at is not None


async def test_delete_prompt_response_as_profile_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a owns the prompt's profile -> may delete the winger's comment.
    response = graph.prompt_response
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert DeletePromptResponse.is_available(response, deps.user, deps) is True

    result = await DeletePromptResponse.execute(response, EmptyActionData(), db_session, deps.user, deps)
    assert result.message == "Comment deleted"


async def test_delete_prompt_response_denied_for_unrelated(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is neither author nor profile owner -> is_available denies (-> 403).
    deps = _deps(db_session, user_id=graph.dater_c.id)
    assert DeletePromptResponse.is_available(graph.prompt_response, deps.user, deps) is False
