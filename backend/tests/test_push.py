from __future__ import annotations

import json
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import generate_es256_keypair
from app.domain.decisions.actions import RecordDirectDecision
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.decisions.schemas import DirectDecisionData
from app.domain.profiles.models import Profile
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.push.client import (
    APNsJWTSigner,
    APNsPushClient,
    LocalPushClient,
    PushSendResult,
    build_push_client,
)
from app.platform.push.queries import null_push_token
from app.platform.push.service import PushService
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import DomainGraph

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.

_KEY_ID = "ABC123KEYID"
_TEAM_ID = "TEAM123456"


def _signer() -> APNsJWTSigner:
    # A real (ephemeral) P-256 PEM stands in for the .p8 contents — same EC key
    # material, so PyJWT signs + verifies it exactly as it would a real APNs key.
    private_pem, _ = generate_es256_keypair()
    return APNsJWTSigner(key=private_pem, key_id=_KEY_ID, team_id=_TEAM_ID)


# ── JWT signing + caching ──────────────────────────────────────────────────────


def test_apns_jwt_has_correct_header_and_payload() -> None:
    token = _signer().token()
    header = jwt.get_unverified_header(token)
    assert header["alg"] == "ES256"
    assert header["kid"] == _KEY_ID

    claims = jwt.decode(token, options={"verify_signature": False})
    assert claims["iss"] == _TEAM_ID
    assert "iat" in claims


def test_apns_jwt_is_cached_not_resigned_per_send() -> None:
    signer = _signer()
    first = signer.token()
    second = signer.token()
    # Same cached token handed out — not re-minted on each call.
    assert first == second


def test_apns_jwt_resigns_after_ttl() -> None:
    signer = _signer()
    first = signer.token()
    # Force the cache past its TTL window; the next call must mint a fresh token.
    signer._issued_at -= 60 * 60  # one hour ago
    second = signer.token()
    assert first != second


# ── Send path: headers / body / URL (httpx mocked) ─────────────────────────────


def _apns_client() -> APNsPushClient:
    cfg = MagicMock()
    cfg.APNS_HOST = "api.sandbox.push.apple.com"
    cfg.APNS_TOPIC = "com.plabrum.wingmate"
    private_pem, _ = generate_es256_keypair()
    cfg.APNS_KEY = private_pem
    cfg.APNS_KEY_ID = _KEY_ID
    cfg.APNS_TEAM_ID = _TEAM_ID
    return APNsPushClient(cfg)


class _MockAsyncClient:
    """Stand-in for httpx.AsyncClient capturing the POST and returning a status."""

    last_init_kwargs: dict = {}
    last_post: dict = {}

    def __init__(self, *, status_code: int):
        self._status_code = status_code

    def __call__(self, **kwargs):
        _MockAsyncClient.last_init_kwargs = kwargs
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, headers, content):
        _MockAsyncClient.last_post = {"url": url, "headers": headers, "content": content}
        resp = MagicMock()
        resp.status_code = self._status_code
        resp.text = ""
        return resp


async def test_send_posts_correct_url_headers_and_body() -> None:
    client = _apns_client()
    mock = _MockAsyncClient(status_code=200)
    with patch("app.platform.push.client.httpx.AsyncClient", mock):
        result = await client.send("DEVICETOKEN123", "Hello", "World")

    assert result == PushSendResult(delivered=True)

    # HTTP/2 was requested (APNs requires it).
    assert _MockAsyncClient.last_init_kwargs.get("http2") is True

    post = _MockAsyncClient.last_post
    assert post["url"] == "https://api.sandbox.push.apple.com/3/device/DEVICETOKEN123"

    headers = post["headers"]
    assert headers["apns-topic"] == "com.plabrum.wingmate"
    assert headers["apns-push-type"] == "alert"
    assert headers["apns-priority"] == "10"
    assert headers["authorization"].startswith("bearer ")

    body = json.loads(post["content"])
    assert body == {"aps": {"alert": {"title": "Hello", "body": "World"}, "sound": "default"}}


async def test_send_410_returns_unregistered() -> None:
    client = _apns_client()
    mock = _MockAsyncClient(status_code=410)
    with patch("app.platform.push.client.httpx.AsyncClient", mock):
        result = await client.send("DEADTOKEN", "Hello", "World")
    assert result == PushSendResult(delivered=False, unregistered=True)


async def test_send_other_error_is_swallowed() -> None:
    client = _apns_client()
    mock = _MockAsyncClient(status_code=400)
    with patch("app.platform.push.client.httpx.AsyncClient", mock):
        result = await client.send("BADTOKEN", "Hello", "World")
    # Log-and-swallow: not delivered, but no raise and not flagged as unregistered.
    assert result == PushSendResult(delivered=False, unregistered=False)


async def test_send_transport_error_is_swallowed() -> None:
    client = _apns_client()

    class _Raising:
        def __call__(self, **kwargs):
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

        async def post(self, *a, **k):
            raise httpx.ConnectError("boom")

    with patch("app.platform.push.client.httpx.AsyncClient", _Raising()):
        result = await client.send("TOK", "t", "b")
    assert result == PushSendResult(delivered=False, unregistered=False)


# ── Client selection ───────────────────────────────────────────────────────────


def test_build_push_client_local_in_testing() -> None:
    cfg = MagicMock()
    cfg.ENV = "testing"
    cfg.APNS_KEY = "irrelevant"
    assert isinstance(build_push_client(cfg), LocalPushClient)


def test_build_push_client_local_when_no_apns_key() -> None:
    cfg = MagicMock()
    cfg.ENV = "production"
    cfg.APNS_KEY = ""
    assert isinstance(build_push_client(cfg), LocalPushClient)


def test_build_push_client_apns_in_prod_with_key() -> None:
    cfg = MagicMock()
    cfg.ENV = "production"
    private_pem, _ = generate_es256_keypair()
    cfg.APNS_KEY = private_pem
    cfg.APNS_KEY_ID = _KEY_ID
    cfg.APNS_TEAM_ID = _TEAM_ID
    cfg.APNS_HOST = "api.push.apple.com"
    cfg.APNS_TOPIC = "com.plabrum.wingmate"
    assert isinstance(build_push_client(cfg), APNsPushClient)


# ── 410 dead-token cleanup (the reap write) ────────────────────────────────────


async def test_null_push_token_clears_matching_profiles(graph: DomainGraph, db_session: AsyncSession) -> None:
    graph.dater_a.push_token = "DEADTOKEN"
    await db_session.flush()

    cleared = await null_push_token(db_session, "DEADTOKEN")
    assert cleared == 1

    refreshed = (
        await db_session.execute(select(Profile.push_token).where(Profile.id == graph.dater_a.id))
    ).scalar_one()
    assert refreshed is None


# ── PushService: 410 enqueues a reap; success does not ─────────────────────────


def _service_with_client(session: AsyncSession, *, unregistered: bool):
    client = MagicMock()
    client.send = AsyncMock(return_value=PushSendResult(delivered=not unregistered, unregistered=unregistered))
    return PushService(client, session, MagicMock())


async def test_push_service_reaps_on_410(db_session: AsyncSession) -> None:
    service = _service_with_client(db_session, unregistered=True)
    with patch("app.platform.push.service.dispatch_task", new=AsyncMock()) as dispatch:
        await service.send("DEADTOKEN", "t", "b")
    dispatch.assert_awaited_once()
    # The reap task is dispatched with the dead token.
    await_args = dispatch.await_args
    assert await_args is not None
    assert await_args.kwargs.get("token") == "DEADTOKEN"


async def test_push_service_no_reap_on_success(db_session: AsyncSession) -> None:
    service = _service_with_client(db_session, unregistered=False)
    with patch("app.platform.push.service.dispatch_task", new=AsyncMock()) as dispatch:
        await service.send("GOODTOKEN", "t", "b")
    dispatch.assert_not_awaited()


# ── A match action triggers a send (the call site is unchanged) ────────────────


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
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
        realtime=MagicMock(),
        media=MagicMock(),
    )


async def test_match_action_fires_push(graph: DomainGraph, db_session: AsyncSession) -> None:
    # Both daters carry a push token so the match fan-out actually sends.
    graph.dater_a.push_token = "TOKEN_A"
    graph.dater_c.push_token = "TOKEN_C"
    await db_session.flush()

    # dater_c already approved dater_a, so dater_a approving dater_c forms a match.
    db_session.add(
        Decision(
            actor_id=graph.dater_c.id,
            recipient_id=graph.dater_a.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = DirectDecisionData(recipientId=graph.dater_c.id, decision=DecisionType.APPROVED)
    await RecordDirectDecision.execute(data, db_session, deps)

    send = cast(AsyncMock, deps.push.send)
    # A match formed -> a push fired to each tokened participant.
    assert send.await_count == 2
    tokens = {call.args[0] for call in send.await_args_list}
    assert tokens == {"TOKEN_A", "TOKEN_C"}
