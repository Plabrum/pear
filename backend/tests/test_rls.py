from __future__ import annotations

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.messages.models import Message
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.domain.prompts.models import ProfilePrompt, PromptResponse
from tests.fixtures.graph import ActingAs, DomainGraph
from tests.fixtures.ids import fake_id

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


# ─────────────────────────────────────────────────────────────────────────────
# matches INSERT — MutualMatchInsert (in-request match formation, no system mode)
# ─────────────────────────────────────────────────────────────────────────────


async def test_participant_forms_match_on_mutual(
    graph: DomainGraph, acting_as: ActingAs, db_session: AsyncSession
) -> None:
    """matches INSERT WITH CHECK passes for a participant once BOTH sides approved.

    Seed dater_a <-> dater_c approving each other (no match yet, system mode), then
    act AS dater_a and insert the ordered row: the policy's two `decisions` EXISTS
    checks are both satisfied under dater_a's own scope, so the insert succeeds.
    """
    db_session.add_all(
        [
            Decision(actor_id=graph.dater_a.id, recipient_id=graph.dater_c.id, state=DecisionState.APPROVED),
            Decision(actor_id=graph.dater_c.id, recipient_id=graph.dater_a.id, state=DecisionState.APPROVED),
        ]
    )
    await db_session.flush()

    lo, hi = sorted([graph.dater_a.id, graph.dater_c.id])
    async with acting_as(graph.dater_a.id) as s:
        s.add(Match(user_a_id=lo, user_b_id=hi))
        await s.flush()  # WITH CHECK passes -> no error.


async def test_participant_cannot_form_match_when_not_mutual(
    graph: DomainGraph, acting_as: ActingAs, db_session: AsyncSession
) -> None:
    """matches INSERT WITH CHECK denies a participant when only ONE side approved.

    Only dater_a -> dater_c is approved; the reverse EXISTS fails, so dater_a's
    attempt to form the pair's match is rejected by the policy.
    """
    db_session.add(Decision(actor_id=graph.dater_a.id, recipient_id=graph.dater_c.id, state=DecisionState.APPROVED))
    await db_session.flush()

    lo, hi = sorted([graph.dater_a.id, graph.dater_c.id])
    async with acting_as(graph.dater_a.id) as s:
        await _assert_rls_denies_insert(s, "matches", {"id": fake_id(), "user_a_id": lo, "user_b_id": hi})


async def test_non_participant_cannot_forge_match(graph: DomainGraph, acting_as: ActingAs) -> None:
    """matches INSERT WITH CHECK denies a non-participant forging a pairing.

    dater_c is neither party to (dater_a, dater_b), so the `current_user_id() IN
    (user_a_id, user_b_id)` clause fails regardless of the pair's decision state.
    """
    lo, hi = sorted([graph.dater_a.id, graph.dater_b.id])
    async with acting_as(graph.dater_c.id) as s:
        await _assert_rls_denies_insert(s, "matches", {"id": fake_id(), "user_a_id": lo, "user_b_id": hi})


async def test_dater_sees_own_messages_only(graph: DomainGraph, acting_as: ActingAs) -> None:
    """messages policy: visible only inside a match you participate in."""
    async with acting_as(graph.dater_a.id) as s:
        assert await _ids(s, Message) == {graph.message.id}

    async with acting_as(graph.dater_b.id) as s:
        # dater_b is the other participant -> also sees the message.
        assert await _ids(s, Message) == {graph.message.id}

    async with acting_as(graph.dater_c.id) as s:
        assert await _count(s, Message) == 0


async def test_dating_profile_floor_is_any_authenticated_actor(graph: DomainGraph, acting_as: ActingAs) -> None:
    """dating_profiles SELECT floor coarsened to USING (current_user_id() IS NOT NULL).

    The DB floor is "any signed-in actor may read the row"; business visibility
    (is_active) moved to the app query layer (profiles.queries). Flip dater_a's
    profile inactive and confirm BOTH the owner and an unrelated authed actor still
    read it at the floor — the inactive gate now lives in the app, not RLS.
    """
    async with acting_as(graph.dater_a.id) as s:
        dp = (await s.execute(select(DatingProfile).where(DatingProfile.id == graph.dating_profile_a.id))).scalar_one()
        dp.is_active = False
        await s.flush()
        # Owner still sees their own inactive profile.
        assert graph.dating_profile_a.id in await _ids(s, DatingProfile)

    async with acting_as(graph.dater_c.id) as s:
        visible = await _ids(s, DatingProfile)
        # An unrelated authed actor now reads the inactive profile at the floor too
        # (the app layer, not RLS, hides inactive profiles from other viewers)...
        assert graph.dating_profile_a.id in visible
        # ...alongside every other profile.
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
                state=DecisionState.PENDING,
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
                "id": fake_id(),
                "actor_id": graph.dater_c.id,
                "recipient_id": graph.dater_b.id,
                "state": DecisionState.PENDING.name,
                "suggested_by": graph.winger.id,
            },
        )


async def test_winger_decision_insert_floor_ignores_suggested_by(graph: DomainGraph, acting_as: ActingAs) -> None:
    """decisions INSERT floor coarsened to OwnerOrWinger(actor_id).

    The floor is "the actor, or an active wingperson of the actor" — it no longer
    inspects `suggested_by`. So an ACTIVE winger for dater_a may insert a decision on
    dater_a's behalf even with `suggested_by` NULL; the self-vs-suggestion shape is
    enforced by the decisions actions, not the RLS floor. Use a fresh recipient to
    avoid the unique(actor, recipient) constraint.
    """
    # Raw insert (no RETURNING) so the test exercises only the INSERT WITH CHECK floor
    # — the winger isn't a party to this row, so it isn't SELECT-visible to them.
    async with acting_as(graph.winger.id) as s:
        async with s.begin_nested():
            await s.execute(
                text(
                    "INSERT INTO decisions (id, actor_id, recipient_id, state, suggested_by) "
                    "VALUES (:id, :actor_id, :recipient_id, :state, :suggested_by)"
                ),
                {
                    "id": fake_id(),
                    "actor_id": graph.dater_a.id,
                    "recipient_id": graph.dater_c.id,
                    "state": DecisionState.APPROVED.name,  # TextEnum stores .name
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


async def test_message_insert_floor_is_sender_ownership(graph: DomainGraph, acting_as: ActingAs) -> None:
    """messages INSERT floor coarsened to Owner(sender_id).

    The DB floor only requires "the row's sender is me" — match participation on send
    is enforced by the SendMessage action (is_available), which loads the
    participant-scoped Match first. So a raw insert with one's OWN sender_id passes
    the floor even into a match the actor isn't part of. (The actor can't then read
    the row back: messages SELECT stays ViaMatch.) Raw insert avoids the RETURNING
    SELECT so the test isolates the WITH CHECK floor.
    """
    async with acting_as(graph.dater_c.id) as s:
        async with s.begin_nested():
            await s.execute(
                text("INSERT INTO messages (id, match_id, sender_id, body) VALUES (:id, :match_id, :sender_id, :body)"),
                {"id": fake_id(), "match_id": graph.match.id, "sender_id": graph.dater_c.id, "body": "floor ok"},
            )


async def test_cannot_send_message_as_another_sender(graph: DomainGraph, acting_as: ActingAs) -> None:
    """Even a participant cannot forge sender_id to another user (sender_id = me clause)."""
    async with acting_as(graph.dater_a.id) as s:
        await _assert_rls_denies_insert(
            s,
            "messages",
            {"id": fake_id(), "match_id": graph.match.id, "sender_id": graph.dater_b.id, "body": "forged"},
        )


# ─────────────────────────────────────────────────────────────────────────────
# Row 4 — Photos / prompt_responses: read floor coarsened to any authenticated
# actor; approval/party filtering lives in the app query layer.
# ─────────────────────────────────────────────────────────────────────────────


async def test_photo_read_floor_is_any_authenticated_actor(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profile_photos SELECT floor coarsened to USING (current_user_id() IS NOT NULL).

    The approved/active filtering moved to the app query layer (a public read only
    serves APPROVED photos via `approved_only=True`). At the DB floor, ANY signed-in
    actor reads every photo row — owner, winger, and an unrelated viewer all see both
    the approved and the still-pending photo.
    """
    for actor in (graph.dater_a.id, graph.winger.id, graph.dater_c.id):
        async with acting_as(actor) as s:
            visible = await _ids(s, ProfilePhoto)
            assert graph.approved_photo.id in visible
            assert graph.pending_photo.id in visible


async def test_prompt_response_read_floor_is_any_authenticated_actor(graph: DomainGraph, acting_as: ActingAs) -> None:
    """prompt_responses SELECT floor coarsened to USING (current_user_id() IS NOT NULL),
    mirroring profile_photos — discover surfaces a candidate's approved winger
    commentary to a swiper who is neither the author nor the profile owner.
    Approval filtering moved to the app query layer (only APPROVED responses are
    ever selected for a non-party reader). At the DB floor, ANY signed-in actor
    reads every response row regardless of party or approval state.
    """
    for actor in (graph.winger.id, graph.dater_a.id, graph.dater_c.id):
        async with acting_as(actor) as s:
            assert graph.prompt_response.id in await _ids(s, PromptResponse)


async def test_photo_write_denied_off_floor(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profile_photos write floor (RLSScopedMixin edit=OwnerOrWinger): INSERT WITH CHECK
    owner_id = me OR is_active_wingperson(owner_id). An unrelated dater (dater_c)
    inserting a photo owned by dater_a is off the floor -> denied."""
    async with acting_as(graph.dater_c.id) as s:
        await _assert_rls_denies_insert(
            s,
            "profile_photos",
            {
                "id": fake_id(),
                "dating_profile_id": graph.dating_profile_a.id,
                "owner_id": graph.dater_a.id,
                "media_id": graph.pending_media.id,
                "display_order": 7,
            },
        )


async def test_winger_floor_allows_photo_write(graph: DomainGraph, acting_as: ActingAs) -> None:
    """The widened floor: an ACTIVE wingperson reaches the dater's photo rows for
    write (the coarse floor; the precise approve/reject gating is Python-side). The
    winger UPDATEs dater_a's approved photo display_order under their own scope."""
    async with acting_as(graph.winger.id) as s:
        photo = (await s.execute(select(ProfilePhoto).where(ProfilePhoto.id == graph.approved_photo.id))).scalar_one()
        photo.display_order = 42
        await s.flush()  # floor permits the write -> no error.


async def test_prompt_write_denied_off_floor(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profile_prompts write floor (RLSScopedMixin edit=Owner("owner_id")): INSERT WITH
    CHECK owner_id = me. An unrelated dater inserting a prompt owned by dater_a is off
    the floor -> denied."""
    async with acting_as(graph.dater_a.id) as s:
        template_id = (await s.execute(select(ProfilePrompt.prompt_template_id).limit(1))).scalar_one()
    async with acting_as(graph.dater_c.id) as s:
        await _assert_rls_denies_insert(
            s,
            "profile_prompts",
            {
                "id": fake_id(),
                "dating_profile_id": graph.dating_profile_a.id,
                "owner_id": graph.dater_a.id,
                "prompt_template_id": template_id,
                "answer": "intruder",
            },
        )


async def test_prompt_response_insert_must_be_self_authored(graph: DomainGraph, acting_as: ActingAs) -> None:
    """prompt_responses INSERT WITH CHECK: user_id = me. dater_c cannot forge a
    response authored as dater_a (even pinning profile_owner_id to themselves)."""
    async with acting_as(graph.dater_c.id) as s:
        await _assert_rls_denies_insert(
            s,
            "prompt_responses",
            {
                "id": fake_id(),
                "user_id": graph.dater_a.id,  # not the actor -> WITH CHECK fails
                "profile_owner_id": graph.dater_c.id,
                "profile_prompt_id": graph.profile_prompt.id,
                "message": "forged",
            },
        )


async def test_profile_prompt_read_floor_is_any_authenticated_actor(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profile_prompts SELECT floor coarsened to USING (current_user_id() IS NOT NULL).

    The active-profile gate moved to the app query layer; at the DB floor any signed-in
    actor reads the prompt regardless of the owning profile's active state. An unrelated
    viewer sees it both before and after the owner deactivates the profile.
    """
    async with acting_as(graph.dater_c.id) as s:
        assert graph.profile_prompt.id in await _ids(s, ProfilePrompt)

    async with acting_as(graph.dater_a.id) as s:
        dp = (await s.execute(select(DatingProfile).where(DatingProfile.id == graph.dating_profile_a.id))).scalar_one()
        dp.is_active = False
        await s.flush()
        assert graph.profile_prompt.id in await _ids(s, ProfilePrompt)

    async with acting_as(graph.dater_c.id) as s:
        # Coarsened floor: the now-inactive profile's prompt stays readable at the DB
        # level (the app query layer is what hides inactive profiles from viewers).
        assert graph.profile_prompt.id in await _ids(s, ProfilePrompt)


# ─────────────────────────────────────────────────────────────────────────────
# Row 5 — No contacts link -> public profile fields only, nothing scoped.
# ─────────────────────────────────────────────────────────────────────────────


async def test_no_relationship_sees_only_public_profiles(graph: DomainGraph, acting_as: ActingAs) -> None:
    """profiles SELECT is `USING (true)` (public); everything else is relationship-scoped.

    A brand-new authed actor with no graph ties sees ALL profiles (public) yet
    nothing relationship-scoped: no contacts, decisions, matches, or messages.
    """
    stranger = fake_id()
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
    stranger = fake_id()
    async with acting_as(stranger) as s:
        await _assert_rls_denies_insert(
            s,
            "contacts",
            {
                "id": fake_id(),
                "user_id": graph.dater_a.id,  # not the stranger -> WITH CHECK fails
                "phone_number": "+15555550000",
                "winger_id": None,
                "state": WingpersonStatus.INVITED.name,  # TextEnum stores .name
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


async def test_unset_actor_sees_nothing_on_authenticated_floor_tables(graph: DomainGraph, acting_as: ActingAs) -> None:
    """The coarsened `Authenticated` floor (current_user_id() IS NOT NULL) fails closed.

    `dating_profiles` / `profile_prompts` / `profile_photos` no longer carry a
    public/approved read branch — their floor is "any signed-in actor". With NO actor
    `current_user_id()` is NULL, so the predicate is never true and EVERY row (even
    the approved photo / active profile) is hidden.
    """
    async with acting_as(None) as s:
        assert await _count(s, ProfilePhoto) == 0
        assert await _count(s, ProfilePrompt) == 0
        assert await _count(s, DatingProfile) == 0


async def test_unset_actor_cannot_insert(graph: DomainGraph, acting_as: ActingAs) -> None:
    """With no actor, WITH CHECK predicates referencing current_user_id() reject inserts."""
    async with acting_as(None) as s:
        await _assert_rls_denies_insert(
            s,
            "messages",
            {"id": fake_id(), "match_id": graph.match.id, "sender_id": graph.dater_a.id, "body": "no actor"},
        )
