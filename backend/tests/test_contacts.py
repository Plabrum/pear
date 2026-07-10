from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
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
    fetch_active_wingperson_contacts,
    fetch_incoming_invitation_contacts,
    fetch_incoming_invitations,
    fetch_sent_invitation_contacts,
    fetch_sent_invitations,
    fetch_weekly_counts,
    fetch_winging_for,
    fetch_winging_for_tabs,
)
from app.domain.contacts.schemas import InviteWingpersonData
from app.domain.contacts.transformers import (
    WingingForTabRow,
    row_to_incoming_invitation,
    row_to_sent_invitation,
    row_to_winging_for,
    row_to_wingperson,
    rows_to_winging_for_tabs,
)
from app.domain.dating_profiles.enums import Interest
from app.domain.profiles.enums import Gender
from app.platform.actions.base import EmptyActionData
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType
from app.platform.actions.hydrate import actions_for, resolve_group
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from app.utils.exceptions import UserFacingError
from tests.fixtures.graph import DomainGraph
from tests.fixtures.ids import fake_id
from tests.fixtures.media import local_media

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
        config=app_config,
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


# ── Reads ──────────────────────────────────────────────────────────────────────


async def test_fetch_active_wingpeople(graph: DomainGraph, db_session: AsyncSession) -> None:
    rows = await fetch_active_wingpeople(db_session, graph.dater_a.id)
    assert len(rows) == 1
    dto = row_to_wingperson(rows[0], local_media())
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
    dto = row_to_winging_for(rows[0], local_media())
    assert dto.dater is not None
    assert dto.dater.id == graph.dater_a.id
    # interests come off the joined dating_profile and round-trip as the enum list.
    assert dto.dater.interests is not None
    assert Interest.TRAVEL in dto.dater.interests
    assert dto.dater.bio == graph.dating_profile_a.bio
    # interested_gender comes off the joined dating_profile too — the forward sheet
    # uses it to filter which daters a scouted profile can be suggested to.
    assert dto.dater.interestedGender == list(graph.dating_profile_a.interested_gender)


async def test_fetch_winging_for_tabs(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph's only active edge is winger -> dater_a, so the winger's tabs hold
    # exactly that dater, projected to the minimal {id, name} shape.
    rows = await fetch_winging_for_tabs(db_session, graph.winger.id)
    assert len(rows) == 1
    assert rows[0].id == graph.dater_a.id
    assert rows[0].chosen_name == graph.dater_a.chosen_name

    tabs = rows_to_winging_for_tabs(rows)
    assert len(tabs) == 1
    assert tabs[0].id == graph.dater_a.id
    assert tabs[0].name == graph.dater_a.chosen_name


async def test_fetch_winging_for_tabs_only_active_edges(graph: DomainGraph, db_session: AsyncSession) -> None:
    # An INVITED (not yet active) edge from dater_c must NOT appear as a tab.
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550009",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    rows = await fetch_winging_for_tabs(db_session, graph.winger.id)
    assert [r.id for r in rows] == [graph.dater_a.id]
    # A user who wings for nobody sees an empty list.
    assert await fetch_winging_for_tabs(db_session, graph.dater_c.id) == []


def test_rows_to_winging_for_tabs_dedupes_preserving_order() -> None:
    d1, d2 = fake_id(), fake_id()
    rows = [
        WingingForTabRow(id=d1, chosen_name="Dana", created_at=datetime(2026, 1, 3, tzinfo=UTC)),
        WingingForTabRow(id=d2, chosen_name="Drew", created_at=datetime(2026, 1, 2, tzinfo=UTC)),
        WingingForTabRow(id=d1, chosen_name="Dana", created_at=datetime(2026, 1, 1, tzinfo=UTC)),
    ]
    tabs = rows_to_winging_for_tabs(rows)
    assert [t.id for t in tabs] == [d1, d2]
    assert [t.name for t in tabs] == ["Dana", "Drew"]
    assert rows_to_winging_for_tabs([]) == []


async def test_sent_invitations_and_incoming_reflect_an_invite(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Seed a fresh INVITED contact from dater_c -> winger.
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number=graph.winger.phone_number or "+15555550000",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
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


# ── Reads: hydrated `actions` field (gating projected onto the roster) ────────────


async def test_wingperson_actions_for_owner_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The dater owns one ACTIVE contact; they may [remove] it (no accept/decline —
    # those are winger-only and only while INVITED).
    rows = await fetch_active_wingpeople(db_session, graph.dater_a.id)
    contacts = await fetch_active_wingperson_contacts(db_session, graph.dater_a.id)
    group = resolve_group(ActionGroupType.CONTACT_ACTIONS)
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)

    dto = row_to_wingperson(rows[0], local_media(), actions_for(group, deps, contacts[rows[0].id]))
    assert [a.action for a in dto.actions] == ["contact_actions__remove"]
    assert all(a.action_group_type is ActionGroupType.CONTACT_ACTIONS for a in dto.actions)
    # The remove action carries its target state (ACTIVE -> REMOVED).
    remove = next(a for a in dto.actions if a.action == "contact_actions__remove")
    assert remove.target_state == WingpersonStatus.REMOVED.value


async def test_incoming_invitation_actions_for_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # An INVITED contact addressed to the winger -> the winger sees [accept, decline].
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550010",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    rows = await fetch_incoming_invitations(db_session, graph.winger.id)
    contacts = await fetch_incoming_invitation_contacts(db_session, graph.winger.id)
    group = resolve_group(ActionGroupType.CONTACT_ACTIONS)
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)

    dto = row_to_incoming_invitation(rows[0], actions_for(group, deps, contacts[rows[0].id]))
    assert sorted(a.action for a in dto.actions) == ["contact_actions__accept", "contact_actions__decline"]
    assert all(a.action_group_type is ActionGroupType.CONTACT_ACTIONS for a in dto.actions)


async def test_sent_invitation_actions_for_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    # An INVITED contact the dater sent -> the dater may [remove] (cancel) it. Accept
    # / decline are winger-only, so they do not appear for the sending dater.
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550011",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    rows = await fetch_sent_invitations(db_session, graph.dater_c.id)
    contacts = await fetch_sent_invitation_contacts(db_session, graph.dater_c.id)
    group = resolve_group(ActionGroupType.CONTACT_ACTIONS)
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER)

    dto = row_to_sent_invitation(rows[0], actions_for(group, deps, contacts[rows[0].id]))
    assert [a.action for a in dto.actions] == ["contact_actions__remove"]


async def test_winging_for_is_not_actionable(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The `wingingFor` bucket is the winger's view of daters they swipe for. It stays
    # a plain (non-`Actionable`) row — the contacts machine offers nothing to the
    # winger on an ACTIVE edge — so the schema has no `actions` field at all.
    rows = await fetch_winging_for(db_session, graph.winger.id)
    dto = row_to_winging_for(rows[0], local_media())
    assert not hasattr(dto, "actions")


async def test_action_fetchers_key_by_contact_id_and_scope(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The active-contacts fetcher returns the dater's ACTIVE contact keyed by id;
    # the incoming/sent buckets are empty for a dater with only an active edge.
    active = await fetch_active_wingperson_contacts(db_session, graph.dater_a.id)
    assert set(active) == {graph.contact.id}
    assert active[graph.contact.id].state == WingpersonStatus.ACTIVE

    assert await fetch_incoming_invitation_contacts(db_session, graph.dater_a.id) == {}
    assert await fetch_sent_invitation_contacts(db_session, graph.dater_a.id) == {}


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

    assert InviteWingperson.is_available(deps.user, deps) is True
    result = await InviteWingperson.execute(data, db_session, deps.user, deps)

    assert result.created_id is not None
    contact = (await db_session.execute(select(Contact).where(Contact.id == result.created_id))).scalar_one()
    assert contact.user_id == graph.dater_c.id
    assert contact.winger_id == graph.winger.id  # linked by phone
    assert contact.state == WingpersonStatus.INVITED
    push_send.assert_awaited_once()


async def test_invite_unknown_phone_leaves_winger_unlinked_no_push(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    push_send = AsyncMock()
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER, push_send=push_send)
    data = InviteWingpersonData(phoneNumber="+19998887777")  # no matching profile

    result = await InviteWingperson.execute(data, db_session, deps.user, deps)
    contact = (await db_session.execute(select(Contact).where(Contact.id == result.created_id))).scalar_one()
    assert contact.winger_id is None
    push_send.assert_not_awaited()


async def test_invite_duplicate_raises_user_facing_error(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A second invite to the same phone while a non-removed contact exists is
    # rejected with a user-facing message (shown verbatim on the client).
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER)
    data = InviteWingpersonData(phoneNumber="+19998887777")
    await InviteWingperson.execute(data, db_session, deps.user, deps)

    with pytest.raises(UserFacingError) as excinfo:
        await InviteWingperson.execute(data, db_session, deps.user, deps)
    assert excinfo.value.user_facing is True
    assert excinfo.value.status_code == 409
    assert "already invited" in excinfo.value.detail


async def test_invite_after_removed_contact_is_allowed(graph: DomainGraph, db_session: AsyncSession) -> None:
    # A `removed` contact does not block re-inviting the same phone number.
    removed = Contact(
        user_id=graph.dater_c.id,
        phone_number="+19998887777",
        winger_id=None,
        state=WingpersonStatus.REMOVED,
    )
    db_session.add(removed)
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER)
    data = InviteWingpersonData(phoneNumber="+19998887777")
    result = await InviteWingperson.execute(data, db_session, deps.user, deps)
    assert result.created_id is not None


async def test_accept_invite_transitions_to_active(graph: DomainGraph, db_session: AsyncSession) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550001",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert AcceptInvite.is_available(invited, deps.user, deps) is True
    result = await AcceptInvite.execute(invited, EmptyActionData(), db_session, deps.user, deps)

    assert result.message == "Invitation accepted"
    assert invited.state == WingpersonStatus.ACTIVE
    # synonym keeps both views in sync.
    assert invited.state == WingpersonStatus.ACTIVE


async def test_decline_invite_transitions_to_removed(graph: DomainGraph, db_session: AsyncSession) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550002",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert DeclineInvite.is_available(invited, deps.user, deps) is True
    await DeclineInvite.execute(invited, EmptyActionData(), db_session, deps.user, deps)
    assert invited.state == WingpersonStatus.REMOVED


async def test_remove_active_wingperson_transitions_to_removed(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The graph's contact is ACTIVE and owned by dater_a.
    deps = _deps(db_session, user_id=graph.dater_a.id, role=Role.DATER)
    assert RemoveWingperson.is_available(graph.contact, deps.user, deps) is True
    await RemoveWingperson.execute(graph.contact, EmptyActionData(), db_session, deps.user, deps)
    assert graph.contact.state == WingpersonStatus.REMOVED


# ── Actions: gate denials ───────────────────────────────────────────────────────


async def test_accept_denied_for_dater(graph: DomainGraph, db_session: AsyncSession) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550003",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    # The dater (not the winger) cannot accept their own outgoing invite.
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER)
    assert AcceptInvite.is_available(invited, deps.user, deps) is False


async def test_accept_denied_for_already_active_contact(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger cannot re-accept a contact that is already ACTIVE.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert AcceptInvite.is_available(graph.contact, deps.user, deps) is False


async def test_remove_denied_for_winger(graph: DomainGraph, db_session: AsyncSession) -> None:
    # The winger cannot remove a contact — only the owning dater can.
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    assert RemoveWingperson.is_available(graph.contact, deps.user, deps) is False
