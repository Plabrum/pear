from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.messages.models import Message
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse
from tests.fixtures.graph import ActingAs, DomainGraph

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


async def _ids(session: AsyncSession, model: type) -> set:
    """Return the set of `id`s the current actor can SELECT from `model`."""
    rows = (await session.execute(select(model.id))).scalars().all()
    return set(rows)


async def _count(session: AsyncSession, model: type) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def _assert_rls_denies_insert(session: AsyncSession, table: str, values: dict[str, object]) -> None:
    """Assert that an INSERT into `table` is rejected by an RLS WITH CHECK policy.

    The write is issued as raw SQL (not ORM `add`+`flush`) inside a nested SAVEPOINT
    (`begin_nested`). Two reasons:
      1. A raw `execute` failure raises a `DBAPIError` without poisoning the ORM
         session's flush state (an ORM flush failure would deactivate the whole
         SessionTransaction and force a destructive `rollback()`).
      2. The nested savepoint cleanly rolls back the rejected statement on the
         expected `InsufficientPrivilege`, leaving the seeded graph + session usable
         for the rest of the test and for teardown.
    """
    cols = ", ".join(values)
    params = ", ".join(f":{k}" for k in values)
    stmt = text(f"INSERT INTO {table} ({cols}) VALUES ({params})")
    with pytest.raises((ProgrammingError, DBAPIError)) as excinfo:
        async with session.begin_nested():
            await session.execute(stmt, values)
    # It must be RLS specifically (a policy/privilege error), not a different failure.
    assert "row-level security" in str(excinfo.value).lower(), (
        f"expected an RLS denial inserting into {table}, got: {excinfo.value}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# Row 1 — A dater sees only their own dating profile / matches / messages.
# ─────────────────────────────────────────────────────────────────────────────


async def test_dater_sees_own_match_only(graph: DomainGraph, acting_as: ActingAs) -> None:
    """matches policy: USING (user_a_id = me OR user_b_id = me)."""
    async with acting_as(graph.dater_a.id) as s:
        assert await _ids(s, Match) == {graph.match.id}

    # An unrelated dater (dater_c) shares no match -> sees none.
    async with acting_as(graph.dater_c.id) as s:
        assert await _ids(s, Match) == set()


async def test_dater_sees_own_messages_only(graph: DomainGraph, acting_as: ActingAs) -> None:
    """messages policy: visible only inside a match you participate in."""
    async with acting_as(graph.dater_a.id) as s:
        assert await _ids(s, Message) == {graph.message.id}

    async with acting_as(graph.dater_b.id) as s:
        # dater_b is the other participant -> also sees the message.
        assert await _ids(s, Message) == {graph.message.id}

    async with acting_as(graph.dater_c.id) as s:
        assert await _count(s, Message) == 0


async def test_dating_profile_self_always_visible_to_owner(graph: DomainGraph, acting_as: ActingAs) -> None:
    """dating_profiles policy: USING (is_active OR user_id = me).

    Even an *inactive* profile is visible to its owner. Flip dater_a's profile
    inactive (as owner) and confirm the owner still sees it but a stranger does not.
    """
    async with acting_as(graph.dater_a.id) as s:
        dp = (await s.execute(select(DatingProfile).where(DatingProfile.id == graph.dating_profile_a.id))).scalar_one()
        dp.is_active = False
        await s.flush()
        # Owner still sees their own inactive profile.
        assert graph.dating_profile_a.id in await _ids(s, DatingProfile)

    async with acting_as(graph.dater_c.id) as s:
        visible = await _ids(s, DatingProfile)
        # dater_a's now-inactive profile is hidden from others...
        assert graph.dating_profile_a.id not in visible
        # ...but active profiles (incl. dater_c's own) remain visible.
        assert graph.dating_profile_c.id in visible


# ─────────────────────────────────────────────────────────────────────────────
# Row 2 — Winger reads their dater's rows + acts on their behalf; not others'.
# ─────────────────────────────────────────────────────────────────────────────


async def test_winger_sees_own_contact_link(graph: DomainGraph, acting_as: ActingAs) -> None:
    """contacts policy: USING (user_id = me OR winger_id = me)."""
    async with acting_as(graph.winger.id) as s:
        assert await _ids(s, Contact) == {graph.contact.id}

    async with acting_as(graph.dater_a.id) as s:
        # The dater side of the same contact is also visible to the dater.
        assert graph.contact.id in await _ids(s, Contact)

    async with acting_as(graph.dater_c.id) as s:
        # Unrelated to the contact -> sees none.
        assert await _count(s, Contact) == 0


async def test_winger_sees_suggestion_for_their_dater(graph: DomainGraph, acting_as: ActingAs) -> None:
    """decisions policy: USING (actor=me OR recipient=me OR suggested_by=me).

    The winger suggested a card to dater_a (suggested_by = winger) so the winger
    can read that suggestion row.
    """
    async with acting_as(graph.winger.id) as s:
        assert graph.suggestion.id in await _ids(s, Decision)
        # The winger is not party to dater_a's own approval of dater_b.
        assert graph.decision.id not in await _ids(s, Decision)


async def test_winger_can_insert_decision_for_their_dater(graph: DomainGraph, acting_as: ActingAs) -> None:
    """decisions INSERT: suggested_by = me AND an ACTIVE contact to the actor's dater.

    The winger has an ACTIVE contact for dater_a, so a suggestion authored
    on dater_a's behalf (actor_id = dater_a, suggested_by = winger) passes WITH CHECK.
    Use a fresh recipient to avoid the unique(actor, recipient) constraint.
    """
    async with acting_as(graph.winger.id) as s:
        s.add(
            Decision(
                actor_id=graph.dater_a.id,
                recipient_id=graph.dater_c.id,
                decision=None,
                suggested_by=graph.winger.id,
            )
        )
        await s.flush()  # WITH CHECK passes -> no error.


async def test_winger_cannot_insert_decision_for_unrelated_dater(graph: DomainGraph, acting_as: ActingAs) -> None:
    """decisions INSERT WITH CHECK denies a suggestion for a dater the winger isn't wingperson to.

    The winger has no contact for dater_c, so a suggestion authored on dater_c's
    behalf must be rejected by the policy.
    """
    async with acting_as(graph.winger.id) as s:
        await _assert_rls_denies_insert(
            s,
            "decisions",
            {
                "id": uuid4(),
                "actor_id": graph.dater_c.id,
                "recipient_id": graph.dater_b.id,
                "decision": None,
                "suggested_by": graph.winger.id,
            },
        )


async def test_winger_cannot_impersonate_dater_decision(graph: DomainGraph, acting_as: ActingAs) -> None:
    """A winger cannot insert a decision as if it were the dater's own (suggested_by NULL).

    actor_id = dater_a but suggested_by NULL means "the dater themselves decided".
    The actor (winger) is neither the actor_id nor a valid suggester for a self
    decision, so WITH CHECK fails.
    """
    async with acting_as(graph.winger.id) as s:
        await _assert_rls_denies_insert(
            s,
            "decisions",
            {
                "id": uuid4(),
                "actor_id": graph.dater_a.id,
                "recipient_id": graph.dater_c.id,
                "decision": DecisionType.APPROVED.name,  # TextEnum stores .name
                "suggested_by": None,
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Row 3 — Only match participants read + send messages.
# ─────────────────────────────────────────────────────────────────────────────


async def test_participant_can_send_message(graph: DomainGraph, acting_as: ActingAs) -> None:
    """messages INSERT WITH CHECK: sender_id = me AND I'm a match participant."""
    async with acting_as(graph.dater_b.id) as s:
        s.add(Message(match_id=graph.match.id, sender_id=graph.dater_b.id, body="hello back"))
        await s.flush()


async def test_non_participant_cannot_send_message(graph: DomainGraph, acting_as: ActingAs) -> None:
    """A non-participant (dater_c) cannot insert into someone else's match."""
    async with acting_as(graph.dater_c.id) as s:
        await _assert_rls_denies_insert(
            s,
            "messages",
            {"id": uuid4(), "match_id": graph.match.id, "sender_id": graph.dater_c.id, "body": "intruder"},
        )


async def test_cannot_send_message_as_another_sender(graph: DomainGraph, acting_as: ActingAs) -> None:
    """Even a participant cannot forge sender_id to another user (sender_id = me clause)."""
    async with acting_as(graph.dater_a.id) as s:
        await _assert_rls_denies_insert(
            s,
            "messages",
            {"id": uuid4(), "match_id": graph.match.id, "sender_id": graph.dater_b.id, "body": "forged"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Row 4 — Unapproved photos / prompt_responses: owner + suggester only.
# ─────────────────────────────────────────────────────────────────────────────


async def test_photo_visibility_owner_suggester_and_approved(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profile_photos policy: own dating profile, suggester, or (active + approved).

    - Owner (dater_a) sees both their approved and pending photos.
    - Suggester (winger) sees the pending photo they suggested + the approved one
      (dater_a's profile is active and the approved photo is approved).
    - An unrelated authed viewer (dater_c) sees only the approved photo.
    """
    async with acting_as(graph.dater_a.id) as s:
        assert await _ids(s, ProfilePhoto) == {graph.approved_photo.id, graph.pending_photo.id}

    async with acting_as(graph.winger.id) as s:
        winger_visible = await _ids(s, ProfilePhoto)
        assert graph.pending_photo.id in winger_visible  # suggester
        assert graph.approved_photo.id in winger_visible  # active + approved

    async with acting_as(graph.dater_c.id) as s:
        stranger_visible = await _ids(s, ProfilePhoto)
        assert graph.approved_photo.id in stranger_visible
        assert graph.pending_photo.id not in stranger_visible  # unapproved hidden


async def test_prompt_response_unapproved_owner_and_suggester_only(graph: DomainGraph, acting_as: ActingAs) -> None:
    """prompt_responses SELECT: author (user_id=me) OR the prompt's profile owner.

    The pending response was authored by the winger on dater_a's prompt:
    - winger (author) sees it,
    - dater_a (profile owner) sees it,
    - dater_c (unrelated) does not.
    """
    async with acting_as(graph.winger.id) as s:
        assert graph.prompt_response.id in await _ids(s, PromptResponse)

    async with acting_as(graph.dater_a.id) as s:
        assert graph.prompt_response.id in await _ids(s, PromptResponse)

    async with acting_as(graph.dater_c.id) as s:
        assert graph.prompt_response.id not in await _ids(s, PromptResponse)


async def test_profile_prompt_visible_when_profile_active(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profile_prompts SELECT: profile active OR owner.

    dater_a's profile is active, so any authed viewer sees the prompt; once the
    owner deactivates it, only the owner does.
    """
    async with acting_as(graph.dater_c.id) as s:
        assert graph.profile_prompt.id in await _ids(s, ProfilePrompt)

    async with acting_as(graph.dater_a.id) as s:
        dp = (await s.execute(select(DatingProfile).where(DatingProfile.id == graph.dating_profile_a.id))).scalar_one()
        dp.is_active = False
        await s.flush()
        # Owner still sees their own prompt.
        assert graph.profile_prompt.id in await _ids(s, ProfilePrompt)

    async with acting_as(graph.dater_c.id) as s:
        # Now-inactive profile hides the prompt from others.
        assert graph.profile_prompt.id not in await _ids(s, ProfilePrompt)


# ─────────────────────────────────────────────────────────────────────────────
# Row 5 — No contacts link -> public profile fields only, nothing scoped.
# ─────────────────────────────────────────────────────────────────────────────


async def test_no_relationship_sees_only_public_profiles(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profiles SELECT is `USING (true)` (public); everything else is relationship-scoped.

    A brand-new authed actor with no graph ties sees ALL profiles (public) yet
    nothing relationship-scoped: no contacts, decisions, matches, or messages.
    """
    stranger = uuid4()
    async with acting_as(stranger) as s:
        # Public profile rows are readable...
        profile_ids = await _ids(s, Profile)
        assert {graph.dater_a.id, graph.dater_b.id, graph.dater_c.id, graph.winger.id} <= profile_ids

        # ...but no relationship-scoped rows leak.
        assert await _count(s, Contact) == 0
        assert await _count(s, Decision) == 0
        assert await _count(s, Match) == 0
        assert await _count(s, Message) == 0


async def test_stranger_cannot_write_to_unrelated_profile(graph: DomainGraph, acting_as: ActingAs) -> None:
    """A stranger cannot create a contact owned by someone else (user_id = me clause)."""
    stranger = uuid4()
    async with acting_as(stranger) as s:
        await _assert_rls_denies_insert(
            s,
            "contacts",
            {
                "id": uuid4(),
                "user_id": graph.dater_a.id,  # not the stranger -> WITH CHECK fails
                "phone_number": "+15555550000",
                "winger_id": None,
                "wingperson_status": WingpersonStatus.INVITED.name,  # TextEnum stores .name
            },
        )


# ─────────────────────────────────────────────────────────────────────────────
# Row 6 — app.user_id UNSET -> policies fail closed.
# ─────────────────────────────────────────────────────────────────────────────


async def test_unset_actor_fails_closed_on_scoped_tables(graph: DomainGraph, acting_as: ActingAs) -> None:
    """As `pear_app` with the escape off but NO app.user_id, current_user_id() is NULL.

    Purely relationship-scoped policies (no public branch) compare against
    `current_user_id()`, which is NULL, so the predicate is never true -> zero rows.
    Tables with an intentional public branch (profiles/prompt_templates, and the
    `is_active`-gated dating_profiles/photos/prompts) are covered separately below.
    """
    async with acting_as(None) as s:
        for model in (Contact, Decision, Match, Message, PromptResponse):
            assert await _count(s, model) == 0, f"{model.__name__} leaked rows with no actor"


async def test_unset_actor_hides_private_rows_on_public_branch_tables(graph: DomainGraph, acting_as: ActingAs) -> None:
    """Public-branch tables still hide the owner-only / relationship-only rows.

    `profile_photos` and `profile_prompts` expose a public branch (active profile +
    approved photo / active profile prompt) but the owner/suggester-only rows must
    stay hidden when there is no actor:
      - the *approved* photo on an active profile is visible (public branch),
      - the *pending* photo (owner/suggester only) is NOT.
    """
    async with acting_as(None) as s:
        photo_ids = await _ids(s, ProfilePhoto)
        assert graph.approved_photo.id in photo_ids  # public branch
        assert graph.pending_photo.id not in photo_ids  # owner/suggester only -> denied

    # An inactive dating profile is owner-only; flip it inactive as the owner, then
    # confirm it is hidden when there is no actor.
    async with acting_as(graph.dater_a.id) as s:
        dp = (await s.execute(select(DatingProfile).where(DatingProfile.id == graph.dating_profile_a.id))).scalar_one()
        dp.is_active = False
        await s.flush()
    async with acting_as(None) as s:
        assert graph.dating_profile_a.id not in await _ids(s, DatingProfile)


async def test_unset_actor_cannot_insert(graph: DomainGraph, acting_as: ActingAs) -> None:
    """With no actor, WITH CHECK predicates referencing current_user_id() reject inserts."""
    async with acting_as(None) as s:
        await _assert_rls_denies_insert(
            s,
            "messages",
            {"id": uuid4(), "match_id": graph.match.id, "sender_id": graph.dater_a.id, "body": "no actor"},
        )
