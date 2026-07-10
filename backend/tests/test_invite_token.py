from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from litestar import Request
from litestar.di import Provide
from litestar.testing import AsyncTestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config as app_config
from app.domain.contacts.actions import AcceptInviteByToken, InviteWingperson
from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact, WingpersonInviteToken
from app.domain.contacts.schemas import AcceptInviteByTokenData, InviteWingpersonData
from app.domain.contacts.service import ContactService
from app.factory import create_app
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from app.utils.exceptions import UserFacingError
from tests.factories import ProfileFactory
from tests.fixtures.graph import DomainGraph

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    push = MagicMock()
    push.send = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=app_config,
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


# ── ContactService: mint / preview / finalize ───────────────────────────────────


async def test_issue_and_preview_invite_token(graph: DomainGraph, db_session: AsyncSession) -> None:
    service = ContactService(db=db_session, config=app_config)
    token = await service.issue_invite_token(graph.contact.id)

    contact = await service.preview_invite_token(token)
    assert contact is not None
    assert contact.id == graph.contact.id


async def test_preview_is_not_single_use(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Deliberate divergence from magic-link: preview may be hit repeatedly before
    # the invitee has an account to actually accept with (see ContactService docstring).
    service = ContactService(db=db_session, config=app_config)
    token = await service.issue_invite_token(graph.contact.id)

    first = await service.preview_invite_token(token)
    second = await service.preview_invite_token(token)
    assert first is not None
    assert second is not None
    assert first.id == second.id == graph.contact.id


async def test_preview_unknown_token_rejected(db_session: AsyncSession) -> None:
    service = ContactService(db=db_session, config=app_config)
    assert await service.preview_invite_token("never-issued-token") is None


async def test_preview_expired_token_rejected(graph: DomainGraph, db_session: AsyncSession) -> None:
    service = ContactService(db=db_session, config=app_config)
    token = await service.issue_invite_token(graph.contact.id)

    row = (
        await db_session.execute(
            text("SELECT id FROM wingperson_invite_tokens WHERE token_hash = :h"),
            {"h": service._hash_token(token)},  # noqa: SLF001 — test reaches into the private hash helper
        )
    ).scalar_one()
    token_row = await db_session.get(WingpersonInviteToken, row)
    assert token_row is not None
    token_row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db_session.flush()

    assert await service.preview_invite_token(token) is None


async def test_finalize_is_single_use(graph: DomainGraph, db_session: AsyncSession) -> None:
    service = ContactService(db=db_session, config=app_config)
    token = await service.issue_invite_token(graph.contact.id)

    first = await service.finalize_invite_token(token)
    assert first == graph.contact.id

    second = await service.finalize_invite_token(token)
    assert second is None
    # Preview also fails once finalized — used_at is stamped.
    assert await service.preview_invite_token(token) is None


# ── InviteWingperson: mints a token + URL ───────────────────────────────────────


async def test_invite_wingperson_mints_invite_url(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_c.id, role=Role.DATER)
    data = InviteWingpersonData(phoneNumber="+19998887771")

    result = await InviteWingperson.execute(data, db_session, deps.user, deps)

    assert result.invite_url is not None
    assert result.invite_url.startswith(f"{app_config.UNIVERSAL_LINK_BASE_URL}/invite/verify?token=")

    # The minted token previews to the newly created contact.
    token = result.invite_url.split("token=", 1)[1]
    service = ContactService(db=db_session, config=app_config)
    contact = await service.preview_invite_token(token)
    assert contact is not None
    assert contact.id == result.created_id


# ── AcceptInviteByToken ──────────────────────────────────────────────────────────


async def test_accept_invite_by_token_links_new_winger_and_activates(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550020",
        winger_id=None,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    service = ContactService(db=db_session, config=app_config)
    token = await service.issue_invite_token(invited.id)

    new_winger = await ProfileFactory.create_async(db_session, state=None)
    await db_session.flush()

    deps = _deps(db_session, user_id=new_winger.id, role=Role.WINGER)
    result = await AcceptInviteByToken.execute(AcceptInviteByTokenData(token=token), db_session, deps.user, deps)

    assert result.message == "Invitation accepted"
    assert invited.winger_id == new_winger.id
    assert invited.state == WingpersonStatus.ACTIVE

    # Single-use: a second accept with the same token is rejected.
    with pytest.raises(UserFacingError):
        await AcceptInviteByToken.execute(AcceptInviteByTokenData(token=token), db_session, deps.user, deps)


async def test_accept_invite_by_token_unknown_token_rejected(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.winger.id, role=Role.WINGER)
    with pytest.raises(UserFacingError) as excinfo:
        await AcceptInviteByToken.execute(
            AcceptInviteByTokenData(token="never-issued-token"), db_session, deps.user, deps
        )
    assert excinfo.value.user_facing is True


async def test_accept_invite_by_token_rejects_hijack_by_different_winger(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    # An invite already linked to `graph.winger` cannot be claimed by a stranger.
    invited = Contact(
        user_id=graph.dater_c.id,
        phone_number="+15555550021",
        winger_id=graph.winger.id,
        state=WingpersonStatus.INVITED,
    )
    db_session.add(invited)
    await db_session.flush()

    service = ContactService(db=db_session, config=app_config)
    token = await service.issue_invite_token(invited.id)

    stranger = await ProfileFactory.create_async(db_session, state=None)
    await db_session.flush()

    deps = _deps(db_session, user_id=stranger.id, role=Role.WINGER)
    with pytest.raises(UserFacingError) as excinfo:
        await AcceptInviteByToken.execute(AcceptInviteByTokenData(token=token), db_session, deps.user, deps)
    assert "already been claimed" in excinfo.value.detail
    # The contact is untouched — still linked to the original winger, still INVITED.
    assert invited.winger_id == graph.winger.id
    assert invited.state == WingpersonStatus.INVITED


# ── HTTP: unauthenticated GET/POST /invite/verify ────────────────────────────────


@pytest.fixture
async def invite_app(db_session: AsyncSession) -> AsyncGenerator[AsyncTestClient]:
    """A real app wired to the savepoint `db_session`, for the unauthenticated
    `/invite/verify` routes only — no session/auth wiring needed."""

    async def _test_transaction(request: Request) -> AsyncGenerator[AsyncSession]:
        async with db_session.begin_nested():
            await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
            try:
                yield db_session
            finally:
                await db_session.execute(text("SET LOCAL app.is_system_mode = true"))

    app = create_app(
        app_config,
        dependencies_overrides={
            "db_session": Provide(lambda: db_session, sync_to_thread=False),
            "transaction": Provide(_test_transaction),
        },
    )
    async with AsyncTestClient(app=app) as client:
        client.db_session = db_session  # type: ignore[attr-defined]
        yield client


async def test_invite_verify_redirect_hops_into_app_scheme(invite_app: AsyncTestClient) -> None:
    resp = await invite_app.get(
        "/invite/verify",
        params={"token": "some-token"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "pear://invite?token=some-token"


async def test_invite_verify_post_preview_does_not_consume(graph: DomainGraph, invite_app: AsyncTestClient) -> None:
    db: AsyncSession = invite_app.db_session  # type: ignore[attr-defined]
    service = ContactService(db=db, config=app_config)
    token = await service.issue_invite_token(graph.contact.id)

    first = await invite_app.post("/invite/verify", json={"token": token})
    assert first.status_code == 201
    first_body = first.json()
    assert first_body["alreadyLinked"] is True  # graph.contact already has a winger

    second = await invite_app.post("/invite/verify", json={"token": token})
    assert second.status_code == 201
    assert second.json()["contactId"] == first_body["contactId"]


async def test_invite_verify_post_unknown_token_rejected(invite_app: AsyncTestClient) -> None:
    resp = await invite_app.post("/invite/verify", json={"token": "never-issued-token"})
    assert resp.status_code == 401
