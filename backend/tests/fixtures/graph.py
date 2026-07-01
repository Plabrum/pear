from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from faker import Faker
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.messages.models import Message
from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.enums import Gender, UserRole
from app.domain.profiles.models import Profile
from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate
from app.platform.media.models import Media
from tests.factories import (
    ContactFactory,
    DatingProfileFactory,
    DecisionFactory,
    MatchFactory,
    MediaFactory,
    MessageFactory,
    ProfileFactory,
    ProfilePhotoFactory,
    ProfilePromptFactory,
    PromptResponseFactory,
)

__all__ = [
    "ActingAs",
    "DomainGraph",
    "acting_as",
    "build_domain_graph",
    "graph",
]

# An `async with acting_as(<id>):` callable — switches the session's RLS actor.
ActingAs = Callable[[int | str | None], "_ActorScope"]

# Deterministic so test failures are reproducible run-to-run.
faker = Faker()
Faker.seed(20260613)


@dataclass
class DomainGraph:
    """Handles to every row the graph builder created, for assertions."""

    dater_a: Profile
    dater_b: Profile
    dater_c: Profile  # unrelated to the winger AND to dater_a (no contact, no match)
    winger: Profile
    dating_profile_a: DatingProfile
    dating_profile_b: DatingProfile
    dating_profile_c: DatingProfile  # active, so its public profile is discoverable
    contact: Contact
    suggestion: Decision  # winger-suggested card for dater_a (PENDING)
    decision: Decision  # dater_a approved dater_b
    match: Match  # dater_a <-> dater_b
    message: Message  # sent by dater_a in the match
    approved_media: Media  # READY media backing the approved photo
    pending_media: Media  # READY media backing the pending (winger-suggested) photo
    approved_photo: ProfilePhoto
    pending_photo: ProfilePhoto
    profile_prompt: ProfilePrompt
    prompt_response: PromptResponse


async def _make_profile(session: AsyncSession, *, role: UserRole, gender: Gender) -> Profile:
    return await ProfileFactory.create_async(session, state=role, gender=gender)


async def _make_dating_profile(session: AsyncSession, *, user: Profile) -> DatingProfile:
    return await DatingProfileFactory.create_async(session, user_id=user.id)


async def _make_media(session: AsyncSession, *, owner: Profile) -> Media:
    """A READY media owned by `owner` (file_key + processed WebP), flushed for its id."""
    file_key = f"{owner.id}/{faker.uuid4()}.jpg"
    return await MediaFactory.create_async(session, owner_id=owner.id, file_key=file_key)


async def build_domain_graph(session: AsyncSession) -> DomainGraph:
    """Seed a representative dater/winger/match/message graph and return its rows.

    Must run under a system-mode session (RLS bypassed). `flush`es throughout so
    FK targets have ids; the caller's transaction owns commit/rollback.
    """
    # ── Identities ───────────────────────────────────────────────────────────
    dater_a = await _make_profile(session, role=UserRole.DATER, gender=Gender.MALE)
    dater_b = await _make_profile(session, role=UserRole.DATER, gender=Gender.FEMALE)
    # dater_c stands alone: no contact with the winger, no match with anyone — the
    # "unrelated dater" used to prove relationship-scoped denials.
    dater_c = await _make_profile(session, role=UserRole.DATER, gender=Gender.FEMALE)
    winger = await _make_profile(session, role=UserRole.WINGER, gender=Gender.NON_BINARY)

    dating_profile_a = await _make_dating_profile(session, user=dater_a)
    dating_profile_b = await _make_dating_profile(session, user=dater_b)
    dating_profile_c = await _make_dating_profile(session, user=dater_c)

    # ── Winger ↔ dater_a relationship (active contact) ───────────────────────
    contact = await ContactFactory.create_async(
        session,
        user_id=dater_a.id,
        phone_number=winger.phone_number or faker.numerify("+1##########"),
        winger_id=winger.id,
        state=WingpersonStatus.ACTIVE,
    )

    # ── Winger-suggested card for dater_a (PENDING — not yet acted on) ────────
    suggestion = await DecisionFactory.create_async(
        session,
        actor_id=dater_a.id,
        recipient_id=dater_b.id,
        state=DecisionState.PENDING,
        suggested_by=winger.id,
        note=faker.sentence(nb_words=8),
    )

    # ── dater_a's own approval of dater_b ────────────────────────────────────
    # Distinct (actor, recipient) pair from the suggestion to honor
    # unique_actor_recipient: dater_b is the actor here, dater_a the recipient.
    decision = await DecisionFactory.create_async(
        session,
        actor_id=dater_b.id,
        recipient_id=dater_a.id,
        state=DecisionState.APPROVED,
    )

    # ── Mutual match (ids ordered to satisfy ordered_match_ids CHECK) ────────
    lo, hi = sorted([dater_a.id, dater_b.id])
    match = await MatchFactory.create_async(session, user_a_id=lo, user_b_id=hi)

    message = await MessageFactory.create_async(session, match_id=match.id, sender_id=dater_a.id)

    # ── Media + photos for dater_a: one approved, one pending ────────────────
    # dater_a owns the bytes; the winger only suggests the (already-owner) media.
    approved_media = await _make_media(session, owner=dater_a)
    pending_media = await _make_media(session, owner=dater_a)
    approved_photo = await ProfilePhotoFactory.create_async(
        session,
        dating_profile_id=dating_profile_a.id,
        owner_id=dater_a.id,
        media_id=approved_media.id,
        display_order=0,
        state=PhotoApprovalState.APPROVED,
        approved_at=datetime.now(tz=UTC),
    )
    # Winger-suggested, still pending approval.
    pending_photo = await ProfilePhotoFactory.create_async(
        session,
        dating_profile_id=dating_profile_a.id,
        owner_id=dater_a.id,
        suggester_id=winger.id,
        media_id=pending_media.id,
        display_order=1,
        state=PhotoApprovalState.PENDING,
    )

    # ── Prompt + response (uses a seeded template) ───────────────────────────
    template = (await session.execute(select(PromptTemplate).limit(1))).scalar_one()
    profile_prompt = await ProfilePromptFactory.create_async(
        session,
        dating_profile_id=dating_profile_a.id,
        owner_id=dater_a.id,
        prompt_template_id=template.id,
    )

    # A comment from the winger on dater_a's prompt, pending approval.
    prompt_response = await PromptResponseFactory.create_async(
        session,
        user_id=winger.id,
        profile_owner_id=dater_a.id,
        profile_prompt_id=profile_prompt.id,
        state=ApprovalState.PENDING,
    )

    return DomainGraph(
        dater_a=dater_a,
        dater_b=dater_b,
        dater_c=dater_c,
        winger=winger,
        dating_profile_a=dating_profile_a,
        dating_profile_b=dating_profile_b,
        dating_profile_c=dating_profile_c,
        contact=contact,
        suggestion=suggestion,
        decision=decision,
        match=match,
        message=message,
        approved_media=approved_media,
        pending_media=pending_media,
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


# ─────────────────────────────────────────────────────────────────────────────
# RLS actor switching
# ─────────────────────────────────────────────────────────────────────────────
#
# `db_session` connects as the NON-superuser `pear_app` role (the app's runtime
# role) and sets `app.is_system_mode = true`, so the graph above seeds with RLS
# bypassed via the *honored escape* (NOT a superuser connection — `pear_app` is
# fully subject to FORCE RLS). To *assert* RLS we drop that escape
# (`app.is_system_mode = false`) and set `app.user_id = '<actor>'`, exactly
# mirroring `app/utils/deps.py:provide_transaction`. `public.current_user_id()`
# then reads `app.user_id`, and every policy evaluates against that actor.
#
# There is no `SET ROLE` anymore: the connection role *is* the non-superuser
# `pear_app` role throughout. Because the whole test lives in one savepoint-isolated
# transaction, the actor is switched in place and restored to system mode on exit
# so later fixture writes still work.


class _ActorScope:
    """Async context manager that runs a block as one RLS actor, then restores."""

    def __init__(self, session: AsyncSession, actor: int | str | None) -> None:
        self._session = session
        # `None` => leave `app.user_id` UNSET (fail-closed test): no actor is
        # established. Validate any non-None actor as an int before inlining
        # (SET LOCAL rejects bind params), so this can never become an injection
        # vector.
        self._actor = str(int(actor)) if actor is not None else None

    async def __aenter__(self) -> AsyncSession:
        # Drop the system-mode escape, then (optionally) establish the actor.
        # `SET LOCAL` takes no bind parameters, so the validated int is inlined.
        await self._session.execute(text("SET LOCAL app.is_system_mode = false"))
        if self._actor is not None:
            await self._session.execute(text(f"SET LOCAL app.user_id = {self._actor}"))
        else:
            # Explicitly clear any actor left over from a previous scope.
            await self._session.execute(text("SET LOCAL app.user_id = ''"))
        return self._session

    async def __aexit__(self, *_exc: object) -> None:
        # Restore system mode so the outer fixture transaction (and any follow-on
        # seeding) is unaffected by this scope.
        await self._session.execute(text("SET LOCAL app.user_id = ''"))
        await self._session.execute(text("SET LOCAL app.is_system_mode = true"))


@pytest.fixture
def acting_as(db_session: AsyncSession) -> ActingAs:
    """Return `acting_as(actor)` — an `async with` that scopes the session to an RLS actor.

    Usage::

        async with acting_as(graph.dater_a.id) as s:
            rows = (await s.execute(select(Message))).scalars().all()

    Pass `None` to leave `app.user_id` unset (the fail-closed case): the role is
    still `authenticated`, but no actor is established so relationship-scoped
    policies deny.
    """

    def _scope(actor: int | str | None) -> _ActorScope:
        return _ActorScope(db_session, actor)

    return _scope
