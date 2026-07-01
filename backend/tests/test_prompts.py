"""Tests for the ported `prompts` domain.

The original Hono domain shipped no `*.test.ts`, so these are authored fresh to
cover the contract the port must preserve:

  * Reads (the GET handlers' query+transformer path):
      - `fetch_prompt_templates` / `row_to_prompt_template`     -> /prompt-templates
      - `fetch_onboarding_prompt_templates`                     -> /prompt-templates/onboarding
      - `fetch_own_profile_prompts` / `row_to_profile_prompt`   -> /profile-prompts/me
        (prompt + template question + response thread + author)
  * Gated actions (writes):
      - happy path: CreateProfilePrompt / DeleteProfilePrompt; CreatePromptResponse
        (owner, wingperson, match); ApprovePromptResponse (owner, via the state
        machine); DeletePromptResponse (author + owner).
      - gate denial: ApprovePromptResponse.is_available is False for a winger;
        CreatePromptResponse raises 403 for an unrelated user; approve/delete raise
        404 when the caller does not own the prompt's profile.

Reads run against the seeded `graph` under the system-mode `db_session` (RLS is
covered separately by tests/test_rls.py). Actions are driven directly with a
hand-built `ActionDeps`, mirroring tests/test_profiles.py.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

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
    fetch_onboarding_prompt_templates,
    fetch_own_profile_prompts,
    fetch_prompt_templates,
)
from app.domain.prompts.schemas import (
    CreateProfilePromptData,
    CreatePromptResponseData,
)
from app.domain.prompts.state_machine import adapt
from app.domain.prompts.transformers import (
    row_to_profile_prompt,
    row_to_prompt_template,
)
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.models import StateTransitionLog
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


async def test_list_prompt_templates(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_prompt_templates(db_session)
    assert len(rows) > 0
    dtos = [row_to_prompt_template(r) for r in rows]
    # Ordered by question text (matches the Hono asc(question)).
    questions = [d.question for d in dtos]
    assert questions == sorted(questions)
    assert all(d.id is not None and d.question for d in dtos)


async def test_onboarding_prompt_templates_limit(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_onboarding_prompt_templates(db_session, 5)
    assert 1 <= len(rows) <= 5


async def test_get_own_profile_prompts_bundle(graph: DomainGraph, db_session: AsyncSession) -> None:
    bundles = await fetch_own_profile_prompts(db_session, graph.dater_a.id)
    dtos = [row_to_profile_prompt(p, q, r) for p, q, r in bundles]

    # graph seeds 1 prompt with 1 (pending) response carrying its winger author.
    assert len(dtos) == 1
    prompt = dtos[0]
    assert prompt.datingProfileId == graph.dating_profile_a.id
    assert prompt.template.question  # joined template text present
    assert len(prompt.responses) == 1
    resp = prompt.responses[0]
    assert resp.isApproved is False
    assert resp.author is not None and resp.author.id == graph.winger.id
    assert resp.author.chosenName == graph.winger.chosen_name


async def test_get_own_profile_prompts_empty(db_session: AsyncSession) -> None:
    assert await fetch_own_profile_prompts(db_session, uuid4()) == []


# ── Actions: CreateProfilePrompt ─────────────────────────────────────────────────


async def test_create_profile_prompt_inserts(graph: DomainGraph, db_session: AsyncSession) -> None:
    template = (await db_session.execute(select(PromptTemplate).limit(1))).scalar_one()
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreateProfilePromptData(promptTemplateId=template.id, answer="My answer")

    result = await CreateProfilePrompt.execute(data, db_session, deps)
    assert result.created_id is not None

    prompt = (await db_session.execute(select(ProfilePrompt).where(ProfilePrompt.id == result.created_id))).scalar_one()
    assert prompt.answer == "My answer"
    assert prompt.dating_profile_id == graph.dating_profile_a.id


async def test_create_profile_prompt_no_dating_profile(db_session: AsyncSession) -> None:
    # A profile with no dating profile -> 404.
    fresh = ProfileModel(chosen_name="NoDP", role=UserRole.DATER, gender=Gender.FEMALE)
    db_session.add(fresh)
    await db_session.flush()
    template = (await db_session.execute(select(PromptTemplate).limit(1))).scalar_one()

    deps = _deps(db_session, user_id=fresh.id)
    data = CreateProfilePromptData(promptTemplateId=template.id, answer="x")
    with pytest.raises(DatingProfileNotFoundError):
        await CreateProfilePrompt.execute(data, db_session, deps)


# ── Actions: DeleteProfilePrompt ─────────────────────────────────────────────────


async def test_delete_profile_prompt_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert DeleteProfilePrompt.is_available(graph.profile_prompt, deps) is True

    result = await DeleteProfilePrompt.execute(graph.profile_prompt, EmptyActionData(), db_session, deps)
    assert result.message == "Prompt deleted"
    # Soft delete sets `deleted_at`; the production SELECT filter (installed in
    # factory.py) then hides it. The test harness doesn't install that filter, so
    # we assert on the soft-delete marker directly.
    assert graph.profile_prompt.deleted_at is not None


async def test_delete_profile_prompt_denied_for_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A winger is not a dater -> is_available is False (gate denial before execute).
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeleteProfilePrompt.is_available(graph.profile_prompt, deps) is False


async def test_delete_profile_prompt_wrong_owner_404(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b is a dater (passes is_available) but doesn't own dater_a's prompt -> 404.
    deps = _deps(db_session, user_id=graph.dater_b.id)
    assert DeleteProfilePrompt.is_available(graph.profile_prompt, deps) is True
    with pytest.raises(ProfilePromptNotFoundError):
        await DeleteProfilePrompt.execute(graph.profile_prompt, EmptyActionData(), db_session, deps)


# ── Actions: CreatePromptResponse ────────────────────────────────────────────────


async def test_create_prompt_response_as_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="self note")

    result = await CreatePromptResponse.execute(data, db_session, deps)
    assert result.created_id is not None
    row = (await db_session.execute(select(PromptResponse).where(PromptResponse.id == result.created_id))).scalar_one()
    assert row.user_id == graph.dater_a.id
    assert row.message == "self note"
    assert row.is_approved is False


async def test_create_prompt_response_as_active_wingperson(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="winger note")

    result = await CreatePromptResponse.execute(data, db_session, deps)
    assert result.created_id is not None


async def test_create_prompt_response_as_match(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b is matched with dater_a -> may comment on dater_a's prompt.
    deps = _deps(db_session, user_id=graph.dater_b.id)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="match note")
    result = await CreatePromptResponse.execute(data, db_session, deps)
    assert result.created_id is not None


async def test_create_prompt_response_unrelated_403(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c has no contact + no match with dater_a -> 403.
    deps = _deps(db_session, user_id=graph.dater_c.id)
    data = CreatePromptResponseData(profilePromptId=graph.profile_prompt.id, message="nope")
    with pytest.raises(NotWingpersonOrMatchError):
        await CreatePromptResponse.execute(data, db_session, deps)


async def test_create_prompt_response_missing_prompt_404(db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=uuid4())
    data = CreatePromptResponseData(profilePromptId=uuid4(), message="x")
    with pytest.raises(ProfilePromptNotFoundError):
        await CreatePromptResponse.execute(data, db_session, deps)


# ── Actions: ApprovePromptResponse (state machine) ───────────────────────────────


async def test_approve_prompt_response_owner_transitions(graph: DomainGraph, db_session: AsyncSession) -> None:
    response = graph.prompt_response
    deps = _deps(db_session, user_id=graph.dater_a.id)

    # Adapter projects the pending booleans onto ApprovalState.
    assert adapt(response).state is ApprovalState.PENDING
    assert ApprovePromptResponse.is_available(response, deps) is True

    result = await ApprovePromptResponse.execute(response, EmptyActionData(), db_session, deps)
    assert result.message == "Comment approved"

    refreshed = (await db_session.execute(select(PromptResponse).where(PromptResponse.id == response.id))).scalar_one()
    assert refreshed.is_approved is True
    assert refreshed.is_rejected is False

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
    assert ApprovePromptResponse.is_available(graph.prompt_response, deps) is False


async def test_approve_prompt_response_wrong_owner_404(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_b is a dater (passes is_available) but doesn't own the prompt -> 404.
    deps = _deps(db_session, user_id=graph.dater_b.id)
    assert ApprovePromptResponse.is_available(graph.prompt_response, deps) is True
    with pytest.raises(ProfilePromptNotFoundError):
        await ApprovePromptResponse.execute(graph.prompt_response, EmptyActionData(), db_session, deps)


async def test_approve_prompt_response_not_available_when_already_approved(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    graph.prompt_response.is_approved = True
    await db_session.flush()
    deps = _deps(db_session, user_id=graph.dater_a.id)
    # Already approved -> not pending -> is_available is False.
    assert ApprovePromptResponse.is_available(graph.prompt_response, deps) is False


# ── Actions: DeletePromptResponse ────────────────────────────────────────────────


async def test_delete_prompt_response_as_author(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger authored the seeded response -> may delete it.
    response = graph.prompt_response
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeletePromptResponse.is_available(response, deps) is True

    result = await DeletePromptResponse.execute(response, EmptyActionData(), db_session, deps)
    assert result.message == "Comment deleted"
    # Soft delete sets `deleted_at` (the production SELECT filter then hides it).
    assert response.deleted_at is not None


async def test_delete_prompt_response_as_profile_owner(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a owns the prompt's profile -> may delete the winger's comment.
    response = graph.prompt_response
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert DeletePromptResponse.is_available(response, deps) is True

    result = await DeletePromptResponse.execute(response, EmptyActionData(), db_session, deps)
    assert result.message == "Comment deleted"


async def test_delete_prompt_response_unrelated_404(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_c is neither author nor profile owner -> 404.
    deps = _deps(db_session, user_id=graph.dater_c.id)
    assert DeletePromptResponse.is_available(graph.prompt_response, deps) is True
    with pytest.raises(ProfilePromptNotFoundError):
        await DeletePromptResponse.execute(graph.prompt_response, EmptyActionData(), db_session, deps)
