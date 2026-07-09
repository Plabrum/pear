from __future__ import annotations

import re
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from litestar import Request
from litestar.connection import ASGIConnection
from litestar.di import Provide
from litestar.stores.memory import MemoryStore
from litestar.testing import AsyncTestClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config, config
from app.domain.profiles.models import Profile
from app.factory import create_app
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity, MagicLinkToken
from app.platform.auth.principal import User
from app.platform.comms.models.messages import Message
from app.platform.queue.enums import TaskName

# ── EC keypair helpers (Apple test signing key + token minting) ────────────────


def _es256_keypair() -> tuple[str, str]:
    """Return a fresh (private_pem, public_pem) P-256 keypair."""
    key = ec.generate_private_key(ec.SECP256R1())
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


def _apple_token(
    private_pem: str,
    *,
    aud: str,
    iss: str,
    exp_delta: timedelta,
    sub: str = "apple-sub-e2e",
    **extra: Any,
) -> str:
    """Mint an Apple-style identity token signed with the test EC private key."""
    now = datetime.now(UTC)
    claims = {
        "sub": sub,
        "aud": aud,
        "iss": iss,
        "iat": int(now.timestamp()),
        "exp": int((now + exp_delta).timestamp()),
        **extra,
    }
    return jwt.encode(claims, private_pem, algorithm="ES256")


# ── App / client fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def apple_keypair() -> tuple[str, str]:
    """An Apple signing keypair injected as the verifier's test public key."""
    return _es256_keypair()


@pytest.fixture
def auth_config(apple_keypair: tuple[str, str], monkeypatch: pytest.MonkeyPatch) -> Config:
    """Inject the per-test Apple test key onto the module-global `config`.

    The app and its deps read the module-global `config` directly (no DI/state
    threading), so a test mints Apple tokens with `apple_keypair` and patches the
    matching public key + client/issuer onto that singleton; `build_apple_verifier`
    then selects the Local injected-key verifier. monkeypatch restores after the test.
    """
    _, apple_public = apple_keypair
    monkeypatch.setattr(config, "APPLE_CLIENT_ID", "com.plabrum.wingmate")
    monkeypatch.setattr(config, "APPLE_ISSUER", "https://appleid.apple.com")
    monkeypatch.setattr(config, "APPLE_TEST_PUBLIC_KEY", apple_public)
    return config


@pytest.fixture
async def auth_app(
    auth_config: Config,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncTestClient]:
    """Real app wired to the savepoint `db_session` + the injected-key config.

    Cookie sessions: SessionAuth is given an in-memory "sessions" store (no Redis in
    tests) and a `retrieve_user_handler` that rehydrates the principal from the SAME
    savepoint `db_session` the request transaction runs on (so a profile created on
    `/auth/apple` is visible when `/auth/me` rehydrates from the cookie). The
    AsyncTestClient persists the Set-Cookie across requests like a real client.

    The magic-link route's `dispatch_task` is patched to a counting fake so the
    QUEUED email is asserted via the persisted Message row without invoking the
    SEND_EMAIL task (which needs `email_client` ctx).
    """
    sent_emails: list[dict[str, Any]] = []

    async def _fake_dispatch(transaction, request, task_name, *, queue="default", **kwargs):
        if task_name == TaskName.SEND_EMAIL:
            sent_emails.append(kwargs)

    monkeypatch.setattr("app.platform.comms.service.emails.dispatch_task", _fake_dispatch)

    async def _retrieve_user(session: dict, connection: ASGIConnection) -> User | None:
        user_id = session.get("user_id")
        if not user_id:
            return None
        profile = await db_session.get(Profile, user_id)
        return User.from_profile(profile) if profile is not None else None

    # Request-scoped transaction on the savepoint session — mirrors the production
    # `provide_transaction` (app/utils/deps.py) under the non-superuser role model:
    # the connection is the NON-superuser `pear_app` role (no `SET ROLE`), and for
    # an authenticated request we set `app.user_id` + pin the escape OFF.
    #
    # Unauthenticated login routes (apple, magic-link) set no `app.user_id`; their
    # first-login `profiles` INSERT succeeds because
    # `AuthService.find_or_create_identity` scopes `app.user_id` to the NEW profile's
    # own id under the user's own RLS scope. That is the bootstrap behavior this suite
    # exercises end-to-end.
    async def _test_transaction(request: Request) -> AsyncGenerator[AsyncSession]:
        # Switch the RLS actor in place on the shared savepoint session, then RESTORE
        # system mode on exit so the next request/assertion (and fixture seeding) is
        # unaffected. `SET LOCAL` is transaction-scoped (it survives savepoints), so
        # explicit restore (not savepoint rollback) is what keeps requests isolated.
        async with db_session.begin_nested():
            principal = request.scope.get("user")
            await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
            if principal is not None:
                # Authenticated request (/me, /logout): scope to the session user.
                await db_session.execute(text(f"SET LOCAL app.user_id = {int(principal.id)}"))
            try:
                yield db_session
            finally:
                await db_session.execute(text("SET LOCAL app.user_id = ''"))
                await db_session.execute(text("SET LOCAL app.is_system_mode = true"))

    app = create_app(
        auth_config,
        dependencies_overrides={
            "db_session": Provide(lambda: db_session, sync_to_thread=False),
            "transaction": Provide(_test_transaction),
        },
        stores_overrides={"sessions": MemoryStore()},
        retrieve_user_handler_override=_retrieve_user,
    )

    # The session cookie is non-secure under TestConfig, so the plain-HTTP test
    # client persists it across requests like a real client.
    async with AsyncTestClient(app=app) as client:
        # Stash assertion handles on the client for the email tests.
        client.sent_emails = sent_emails  # type: ignore[attr-defined]
        client.db_session = db_session  # type: ignore[attr-defined]
        client.config = auth_config  # type: ignore[attr-defined]
        yield client


# ── Small request helpers ──────────────────────────────────────────────────────


# The raw token is HMAC-hashed at rest, so it exists only inside the emailed link.
# Tests recover it the same way a real user would: by reading it out of the email
# body (here the persisted Message row that the SEND_EMAIL task would have sent).
_TOKEN_RE = re.compile(r"[?&]token=([^\s&\"'<]+)")


async def _token_for_email(client: AsyncTestClient, email: str) -> str:
    """Parse the most recent magic-link token emailed to `email` from its Message row."""
    db: AsyncSession = client.db_session  # type: ignore[attr-defined]
    rows = (
        (
            await db.execute(
                select(Message).where(Message.to_emails.any(email)).order_by(Message.created_at.desc())  # type: ignore[attr-defined]
            )
        )
        .scalars()
        .all()
    )
    for msg in rows:
        match = _TOKEN_RE.search(msg.body_text or "")
        if match is not None:
            return match.group(1)
    raise AssertionError(f"no magic-link token emailed for {email}")


async def _magic_login(client: AsyncTestClient, email: str) -> Any:
    """Request + verify a magic link, returning the verify response (starts a session)."""
    await client.post("/auth/magic-link/request", json={"email": email})
    token = await _token_for_email(client, email)
    return await client.post("/auth/magic-link/verify", json={"token": token})


# ── Apple ──────────────────────────────────────────────────────────────────────


async def test_apple_valid_token_sets_session_cookie(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: Config = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(
        private_pem,
        aud=cfg.APPLE_CLIENT_ID,
        iss=cfg.APPLE_ISSUER,
        exp_delta=timedelta(minutes=5),
        sub="apple-user-1",
        email="apple1@example.com",
        email_verified="true",
    )
    resp = await auth_app.post("/auth/apple", json={"identityToken": token, "fullName": "Ada Lovelace"})
    assert resp.status_code == 201, resp.text
    # No tokens in the body — auth is a cookie session.
    body = resp.json()
    assert "accessToken" not in body and "refreshToken" not in body
    # The session cookie authenticates the follow-up /auth/me.
    me = await auth_app.get("/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["user"]["id"] == body["id"]
    # `fullName` lands on the bootstrap profile as chosen_name.
    assert body["chosenName"] == "Ada Lovelace"

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    identity = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.APPLE,
                AuthIdentity.provider_subject == "apple-user-1",
            )
        )
    ).scalar_one()
    assert str(identity.profile_id) == body["id"]


async def test_apple_session_cookie_authenticates_me(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: Config = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(
        private_pem,
        aud=cfg.APPLE_CLIENT_ID,
        iss=cfg.APPLE_ISSUER,
        exp_delta=timedelta(minutes=5),
        sub="apple-user-me",
    )
    login = await auth_app.post("/auth/apple", json={"identityToken": token})
    assert login.status_code == 201, login.text

    # The persisted cookie authenticates a follow-up /auth/me.
    me = await auth_app.get("/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["user"]["id"] == login.json()["id"]


async def test_apple_same_subject_returns_same_profile(
    auth_app: AsyncTestClient, apple_keypair: tuple[str, str]
) -> None:
    private_pem, _ = apple_keypair
    cfg: Config = auth_app.config  # type: ignore[attr-defined]

    def _tok() -> str:
        return _apple_token(
            private_pem,
            aud=cfg.APPLE_CLIENT_ID,
            iss=cfg.APPLE_ISSUER,
            exp_delta=timedelta(minutes=5),
            sub="apple-user-repeat",
        )

    first = (await auth_app.post("/auth/apple", json={"identityToken": _tok()})).json()
    second = (await auth_app.post("/auth/apple", json={"identityToken": _tok()})).json()
    assert first["id"] == second["id"]


async def test_apple_wrong_aud_rejected(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: Config = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(private_pem, aud="someone.else", iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=5))
    resp = await auth_app.post("/auth/apple", json={"identityToken": token})
    assert resp.status_code == 401
    # The rejected login does not establish an authenticated session.
    me = await auth_app.get("/auth/me")
    assert me.status_code in (401, 403)


async def test_apple_expired_rejected(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: Config = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(private_pem, aud=cfg.APPLE_CLIENT_ID, iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=-5))
    resp = await auth_app.post("/auth/apple", json={"identityToken": token})
    assert resp.status_code == 401


async def test_apple_tampered_signature_rejected(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: Config = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(private_pem, aud=cfg.APPLE_CLIENT_ID, iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=5))
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    resp = await auth_app.post("/auth/apple", json={"identityToken": tampered})
    assert resp.status_code == 401


# ── Magic link ─────────────────────────────────────────────────────────────────


async def test_magic_link_request_enqueues_one_email_and_204(auth_app: AsyncTestClient) -> None:
    email = "dater-ml@example.com"
    resp = await auth_app.post("/auth/magic-link/request", json={"email": email})
    assert resp.status_code == 204

    # Exactly one email dispatched (the SEND_EMAIL task), and a Message row persisted.
    assert len(auth_app.sent_emails) == 1  # type: ignore[attr-defined]

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    # `email = ANY(to_emails)` — the Postgres array membership operator.
    rows = (
        (
            await db.execute(select(Message).where(Message.to_emails.any(email)))  # type: ignore[attr-defined]
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].template_name == "magic_link"
    assert rows[0].subject == "Sign in to Pear"


async def test_magic_link_unknown_email_same_response_no_leak(auth_app: AsyncTestClient) -> None:
    # A never-seen email returns the SAME 204 as a known one (no existence leak).
    resp = await auth_app.post("/auth/magic-link/request", json={"email": "stranger@example.com"})
    assert resp.status_code == 204


async def test_magic_link_verify_sets_session_then_replay_rejected(auth_app: AsyncTestClient) -> None:
    email = "ml-verify@example.com"
    await auth_app.post("/auth/magic-link/request", json={"email": email})
    token = await _token_for_email(auth_app, email)

    # First verify succeeds and starts a cookie session for the email identity.
    first = await auth_app.post("/auth/magic-link/verify", json={"token": token})
    assert first.status_code == 201, first.text
    body = first.json()
    assert "accessToken" not in body and "refreshToken" not in body
    # The session cookie authenticates the follow-up /auth/me.
    me = await auth_app.get("/auth/me")
    assert me.status_code == 200, me.text
    assert me.json()["user"]["id"] == body["id"]

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    identity = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.EMAIL,
                AuthIdentity.provider_subject == email,
            )
        )
    ).scalar_one()
    assert str(identity.profile_id) == body["id"]

    # Replay of the consumed token is rejected.
    replay = await auth_app.post("/auth/magic-link/verify", json={"token": token})
    assert replay.status_code == 401


async def test_magic_link_expired_token_rejected(auth_app: AsyncTestClient) -> None:
    email = "ml-expired@example.com"
    await auth_app.post("/auth/magic-link/request", json={"email": email})
    token = await _token_for_email(auth_app, email)

    # Force the persisted token's expiry into the past.
    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    row = (await db.execute(select(MagicLinkToken).where(MagicLinkToken.email == email))).scalar_one()
    row.expires_at = datetime.now(UTC) - timedelta(seconds=1)
    await db.flush()

    resp = await auth_app.post("/auth/magic-link/verify", json={"token": token})
    assert resp.status_code == 401


async def test_magic_link_request_rate_limited(auth_app: AsyncTestClient) -> None:
    # The built-in RateLimitConfig middleware allows 3 requests/minute per IP; the
    # 4th is rejected with 429 (per-app in-memory counter, fresh for this test).
    for _ in range(3):
        ok = await auth_app.post("/auth/magic-link/request", json={"email": "rl@example.com"})
        assert ok.status_code == 204, ok.text
    throttled = await auth_app.post("/auth/magic-link/request", json={"email": "rl@example.com"})
    assert throttled.status_code == 429


async def test_magic_link_unknown_token_rejected(auth_app: AsyncTestClient) -> None:
    # A token that was never issued hashes to nothing on file → 401 (no leak/500).
    resp = await auth_app.post("/auth/magic-link/verify", json={"token": "never-issued-token"})
    assert resp.status_code == 401


async def test_magic_link_verify_redirect_hops_into_app_scheme(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.get(
        "/auth/magic-link/verify",
        params={"token": "some-token"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "pear://magic-link?token=some-token"


# ── /auth/me + logout (cookie session) ─────────────────────────────────────────


async def test_me_with_session_returns_user(auth_app: AsyncTestClient) -> None:
    login = (await _magic_login(auth_app, "me-valid@example.com")).json()
    resp = await auth_app.get("/auth/me")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["id"] == login["id"]
    # A freshly-bootstrapped user has no dating profile yet — the gate uses this
    # to route into onboarding.
    assert body["hasDatingProfile"] is False


async def test_me_without_session_rejected(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.get("/auth/me")
    assert resp.status_code in (401, 403)


async def test_logout_clears_session(auth_app: AsyncTestClient) -> None:
    await _magic_login(auth_app, "logout-clear@example.com")

    resp = await auth_app.post("/auth/logout")
    assert resp.status_code == 204

    after = await auth_app.get("/auth/me")
    assert after.status_code in (401, 403)


async def test_logout_requires_session(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.post("/auth/logout")
    assert resp.status_code in (401, 403)
