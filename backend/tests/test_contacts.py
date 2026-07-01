"""Tests for the ported `contacts` (wingperson roster) domain.

The original Hono domain shipped no `*.test.ts`, so these are authored fresh to
cover the contract the port must preserve:

  * Reads (the GET /wingpeople aggregate's query + transformer path):
      - active wingpeople (dater's view)         -> wingpeople[]
      - incoming invitations (winger's view)     -> invitations[]
      - sent invitations (dater's view)          -> sentInvitations[]
      - winging-for (winger's view, w/ interests)-> wingingFor[]
      - weekly suggestion counts (contactId map) -> weeklyCounts
  * Gated actions (writes):
      - happy path: InviteWingperson inserts (and links winger_id by phone);
        AcceptInvite moves invited -> active; DeclineInvite & RemoveWingperson
        move -> removed, all through the state machine.
      - gate denial: AcceptInvite.is_available is False for the dater (winger-only)
        and for an already-active contact; RemoveWingperson denied for a winger.

Reads run against the seeded `graph` under the system-mode `db_session` (RLS is
covered separately by tests/test_rls.py). Actions are driven directly with a
hand-built `ActionDeps`, mirroring tests/test_profiles.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.contacts.actions import (
    AcceptInvite,
    DeclineInvite,
    InviteWingperson,
    RemoveWingperson,
)
from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.contacts.queries import (
    fetch_active_wingpeople,
    fetch_incoming_invitations,
    fetch_sent_invitations,
    fetch_weekly_counts,
    fetch_winging_for,
)
from app.domain.contacts.schemas import InviteWingpersonData
from app.domain.contacts.transformers import (
    row_to_sent_invitation,
    row_to_winging_for,
    row_to_wingperson,
)
from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER, push_send: AsyncMock | None = None) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor.

    Pass `push_send` (an AsyncMock) to make the invite action's `push.send`
    awaitable + assertable; otherwise a default AsyncMock is used.
    """
    push = MagicMock()
    push.send = push_send if push_send is not None else AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


# ── Reads ──────────────────────────────────────────────────────────────────────


async def test_fetch_active_wingpeople(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_active_wingpeople(db_session, graph.dater_a.id)
    assert len(rows) == 1
    dto = row_to_wingperson(rows[0])
    assert dto.id == graph.contact.id
    assert dto.createdAt  # ISO string present
    assert dto.winger is not None
    assert dto.winger.id == graph.winger.id
    assert dto.winger.chosenName == graph.winger.chosen_name
    # gender serializes by .value through msgspec -> matches the Zod enum wire form.
    assert dto.winger.gender is Gender.NON_BINARY


async def test_fetch_incoming_invitations_empty_when_active(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph's only contact is ACTIVE, so the winger has no INVITED rows.
    rows = await fetch_incoming_invitations(db_session, graph.winger.id)
    assert rows == []


async def test_fetch_winging_for(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_winging_for(db_session, graph.winger.id)
    assert len(rows) == 1
    dto = row_to_winging_for(rows[0])
    assert dto.dater is not None
    assert dto.dater.id == graph.dater_a.id
    # interests come off the joined dating_profile and round-trip as the enum list.
    assert dto.dater.interests is not None
    assert Interest.TRAVEL in dto.dater.interests
    assert dto.dater.bio == graph.dating_profile_a.bio


async def test_sent_invitations_and_incoming_reflect_an_invite(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed a fresh INVITED contact from dater_c -> winger.
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number=graph.winger.phone_number or "+15555550000",
        winger_id=graph.winger.id,
        wingperson_status=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    sent = await fetch_sent_invitations(db_session, graph.dater_c.id)
    assert len(sent) == 1
    sdto = row_to_sent_invitation(sent[0])
    assert sdto.id == invited.id
    assert sdto.phoneNumber == invited.phone_number
    assert sdto.winger is not None and sdto.winger.id == graph.winger.id

    incoming = await fetch_incoming_invitations(db_session, graph.winger.id)
    assert [r.id for r in incoming] == [invited.id]


async def test_weekly_counts_counts_recent_suggestions(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph seeds one winger-suggested card for dater_a (suggested_by=winger,
    # created just now), so the active winger's contact should have a count of 1.
    wingpeople = await fetch_active_wingpeople(db_session, graph.dater_a.id)
    counts = await fetch_weekly_counts(db_session, graph.dater_a.id, wingpeople)
    assert counts == {str(graph.contact.id): 1}


# ── Actions: happy path ─────────────────────────────────────────────────────────


async def test_invite_inserts_and_links_existing_profile_and_pushes(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    # dater_c invites the winger by their existing phone number -> winger_id linked,
    # push fired. Give the winger a push token so the (token-guarded) push path runs.
    graph.winger.push_token = "ExpoPushToken[winger]"
    await db_session.flush()

    push_send = AsyncMock()
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER, push_send=push_send)
    data = InviteWingpersonData(phoneNumber=graph.winger.phone_number or "")

    assert InviteWingperson.is_available(deps) is True
    result = await InviteWingperson.execute(data, db_session, deps)

    assert result.created_id is not None
    contact = (await db_session.execute(select(Contact).where(Contact.id == result.created_id))).scalar_one()
    assert contact.user_id == graph.dater_c.id
    assert contact.winger_id == graph.winger.id  # linked by phone
    assert contact.wingperson_status == WingpersonStatus.INVITED
    push_send.assert_awaited_once()


async def test_invite_unknown_phone_leaves_winger_unlinked_no_push(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    push_send = AsyncMock()
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER, push_send=push_send)
    data = InviteWingpersonData(phoneNumber="+19998887777")  # no matching profile

    result = await InviteWingperson.execute(data, db_session, deps)
    contact = (await db_session.execute(select(Contact).where(Contact.id == result.created_id))).scalar_one()
    assert contact.winger_id is None
    push_send.assert_not_awaited()


async def test_accept_invite_transitions_to_active(graph: DomainGraph, db_session: AsyncSession) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550001",
        winger_id=graph.winger.id,
        wingperson_status=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert AcceptInvite.is_available(invited, deps) is True
    result = await AcceptInvite.execute(invited, EmptyActionData(), db_session, deps)

    assert result.message == "Invitation accepted"
    assert invited.wingperson_status == WingpersonStatus.ACTIVE
    # synonym keeps both views in sync.
    assert invited.state == WingpersonStatus.ACTIVE


async def test_decline_invite_transitions_to_removed(graph: DomainGraph, db_session: AsyncSession) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550002",
        winger_id=graph.winger.id,
        wingperson_status=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeclineInvite.is_available(invited, deps) is True
    await DeclineInvite.execute(invited, EmptyActionData(), db_session, deps)
    assert invited.wingperson_status == WingpersonStatus.REMOVED


async def test_remove_active_wingperson_transitions_to_removed(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph's contact is ACTIVE and owned by dater_a.
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)
    assert RemoveWingperson.is_available(graph.contact, deps) is True
    await RemoveWingperson.execute(graph.contact, EmptyActionData(), db_session, deps)
    assert graph.contact.wingperson_status == WingpersonStatus.REMOVED


# ── Actions: gate denials ───────────────────────────────────────────────────────


async def test_accept_denied_for_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550003",
        winger_id=graph.winger.id,
        wingperson_status=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    # The dater (not the winger) cannot accept their own outgoing invite.
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER)
    assert AcceptInvite.is_available(invited, deps) is False


async def test_accept_denied_for_already_active_contact(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger cannot re-accept a contact that is already ACTIVE.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert AcceptInvite.is_available(graph.contact, deps) is False


async def test_remove_denied_for_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger cannot remove a contact — only the owning dater can.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert RemoveWingperson.is_available(graph.contact, deps) is False
