"""Faker-based domain graph fixture for the Phase-4 RLS test suite.

Builds a small but representative slice of the Pear relationship graph so RLS
policy tests (Phase 4) have realistic, related rows to assert visibility against:

    dater_a ─┐
             ├─ (active contact) ── winger          winger suggested a card to dater_a
    dater_b ─┘                                       (decision row, suggested_by=winger)

    dater_a ── decision(approved) ── dater_b ── match ── message
    dater_a profile: 1 approved photo + 1 pending photo
    dater_a profile: 1 profile_prompt (from the seeded templates) + 1 prompt_response

The graph is seeded via the system-mode `db_session` fixture (RLS bypassed), so
factories can write freely; RLS-scoped assertions then use the `transaction`
fixture (or a fresh scoped session) set to one of the graph's user ids.

Lives under `tests/fixtures/` so prod model/seed discovery never sees it. Exposed
as the `graph` pytest fixture (returns a `DomainGraph` dataclass of the created
rows) and re-exported through `tests/fixtures/__init__.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from faker import Faker
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.enums import City, DatingStatus, Interest, Religion
from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.messages.models import Message
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.enums import Gender, UserRole
from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate

__all__ = ["DomainGraph", "build_domain_graph", "graph"]

# Deterministic so test failures are reproducible run-to-run.
faker = Faker()
Faker.seed(20260613)


@dataclass
class DomainGraph:
    """Handles to every row the graph builder created, for assertions."""

    dater_a: Profile
    dater_b: Profile
    winger: Profile
    dating_profile_a: DatingProfile
    dating_profile_b: DatingProfile
    contact: Contact
    suggestion: Decision  # winger-suggested card for dater_a (decision IS NULL)
    decision: Decision  # dater_a approved dater_b
    match: Match  # dater_a <-> dater_b
    message: Message  # sent by dater_a in the match
    approved_photo: ProfilePhoto
    pending_photo: ProfilePhoto
    profile_prompt: ProfilePrompt
    prompt_response: PromptResponse


async def _make_profile(session: AsyncSession, *, role: UserRole, gender: Gender) -> Profile:
    profile = Profile(
        chosen_name=faker.first_name(),
        last_name=faker.last_name(),
        phone_number=faker.numerify("+1##########"),
        date_of_birth=faker.date_of_birth(minimum_age=22, maximum_age=40),
        gender=gender,
        role=role,
    )
    session.add(profile)
    await session.flush()
    return profile


async def _make_dating_profile(session: AsyncSession, *, user: Profile) -> DatingProfile:
    dp = DatingProfile(
        user_id=user.id,
        bio=faker.sentence(nb_words=12),
        interested_gender=[Gender.MALE, Gender.FEMALE],
        age_from=24,
        age_to=38,
        religion=Religion.AGNOSTIC,
        interests=[Interest.TRAVEL, Interest.FOOD, Interest.MUSIC],
        city=City.BOSTON,
        is_active=True,
        dating_status=DatingStatus.OPEN,
    )
    session.add(dp)
    await session.flush()
    return dp


async def build_domain_graph(session: AsyncSession) -> DomainGraph:
    """Seed a representative dater/winger/match/message graph and return its rows.

    Must run under a system-mode session (RLS bypassed). `flush`es throughout so
    FK targets have ids; the caller's transaction owns commit/rollback.
    """
    # ── Identities ───────────────────────────────────────────────────────────
    dater_a = await _make_profile(session, role=UserRole.DATER, gender=Gender.MALE)
    dater_b = await _make_profile(session, role=UserRole.DATER, gender=Gender.FEMALE)
    winger = await _make_profile(session, role=UserRole.WINGER, gender=Gender.NON_BINARY)

    dating_profile_a = await _make_dating_profile(session, user=dater_a)
    dating_profile_b = await _make_dating_profile(session, user=dater_b)

    # ── Winger ↔ dater_a relationship (active contact) ───────────────────────
    contact = Contact(
        user_id=dater_a.id,
        phone_number=winger.phone_number or faker.numerify("+1##########"),
        winger_id=winger.id,
        wingperson_status=WingpersonStatus.ACTIVE,
    )
    session.add(contact)

    # ── Winger-suggested card for dater_a (pending: decision IS NULL) ─────────
    suggestion = Decision(
        actor_id=dater_a.id,
        recipient_id=dater_b.id,
        decision=None,
        suggested_by=winger.id,
        note=faker.sentence(nb_words=8),
    )

    # ── dater_a's own approval of dater_b ────────────────────────────────────
    # Distinct (actor, recipient) pair from the suggestion to honor
    # unique_actor_recipient: dater_b is the actor here, dater_a the recipient.
    decision = Decision(
        actor_id=dater_b.id,
        recipient_id=dater_a.id,
        decision=DecisionType.APPROVED,
        suggested_by=None,
        note=None,
    )
    session.add_all([suggestion, decision])
    await session.flush()

    # ── Mutual match (ids ordered to satisfy ordered_match_ids CHECK) ────────
    lo, hi = sorted([dater_a.id, dater_b.id], key=str)
    match = Match(user_a_id=lo, user_b_id=hi)
    session.add(match)
    await session.flush()

    message = Message(
        match_id=match.id,
        sender_id=dater_a.id,
        body=faker.sentence(nb_words=10),
        is_read=False,
    )
    session.add(message)

    # ── Photos for dater_a: one approved, one pending ────────────────────────
    approved_photo = ProfilePhoto(
        dating_profile_id=dating_profile_a.id,
        suggester_id=None,  # self-uploaded
        storage_url=faker.image_url(),
        display_order=0,
        approved_at=datetime.now(tz=UTC),
    )
    # Winger-suggested, still pending approval.
    pending_photo = ProfilePhoto(
        dating_profile_id=dating_profile_a.id,
        suggester_id=winger.id,
        storage_url=faker.image_url(),
        display_order=1,
        approved_at=None,
    )
    session.add_all([approved_photo, pending_photo])

    # ── Prompt + response (uses a seeded template) ───────────────────────────
    template = (await session.execute(select(PromptTemplate).limit(1))).scalar_one()
    profile_prompt = ProfilePrompt(
        dating_profile_id=dating_profile_a.id,
        prompt_template_id=template.id,
        answer=faker.sentence(nb_words=9),
    )
    session.add(profile_prompt)
    await session.flush()

    # A comment from the winger on dater_a's prompt, pending approval.
    prompt_response = PromptResponse(
        user_id=winger.id,
        profile_prompt_id=profile_prompt.id,
        message=faker.sentence(nb_words=7),
        is_approved=False,
        is_rejected=False,
    )
    session.add(prompt_response)
    await session.flush()

    return DomainGraph(
        dater_a=dater_a,
        dater_b=dater_b,
        winger=winger,
        dating_profile_a=dating_profile_a,
        dating_profile_b=dating_profile_b,
        contact=contact,
        suggestion=suggestion,
        decision=decision,
        match=match,
        message=message,
        approved_photo=approved_photo,
        pending_photo=pending_photo,
        profile_prompt=profile_prompt,
        prompt_response=prompt_response,
    )


@pytest.fixture
async def graph(db_session: AsyncSession) -> DomainGraph:
    """A small dater/winger/match/message graph seeded in system mode.

    Seed with this (RLS bypassed), then switch to the `transaction` fixture (or a
    user-scoped session) to assert RLS visibility against the graph's user ids.
    """
    return await build_domain_graph(db_session)
