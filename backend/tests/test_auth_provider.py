from __future__ import annotations

import time
from collections.abc import AsyncGenerator
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from litestar import Request
from litestar.di import Provide
from litestar.testing import AsyncTestClient
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import TestConfig
from app.factory import create_app
from app.platform.auth.deps import _magic_link_store_for
from app.platform.auth.enums import AuthProvider
from app.platform.auth.magic_link import InMemoryMagicLinkStore
from app.platform.auth.models import AuthIdentity, RefreshToken
from app.platform.auth.tokens import TokenService, hash_refresh_token
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
    """A dedicated Apple signing keypair (distinct from the JWT access-token pair)."""
    return _es256_keypair()


@pytest.fixture
def auth_config(test_config: TestConfig, apple_keypair: tuple[str, str]) -> TestConfig:
    """A per-test TestConfig: ephemeral JWT keypair + injected Apple test key.

    A FRESH config object per test so the per-config memoized magic-link store and
    rate limiter (`auth/deps.py` keys them by `id(config)`) start empty each test —
    no token / counter bleed across tests.
    """
    _, apple_public = apple_keypair
    cfg = TestConfig()
    # Reuse the session keypair so signing/verifying is stable across the test.
    cfg.JWT_SIGNING_KEY = test_config.JWT_SIGNING_KEY
    cfg.JWT_PUBLIC_KEY = test_config.JWT_PUBLIC_KEY
    cfg.APPLE_CLIENT_ID = "com.plabrum.wingmate"
    cfg.APPLE_ISSUER = "https://appleid.apple.com"
    cfg.APPLE_TEST_PUBLIC_KEY = apple_public
    cfg.API_BASE_URL = "http://testserver"
    cfg.APP_DEEP_LINK_SCHEME = "pear"
    cfg.DEV_MAGIC_LINK_EMAIL = ""  # exercise the real send path (patched dispatch)
    return cfg


@pytest.fixture
async def auth_app(
    auth_config: TestConfig,
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> AsyncGenerator[AsyncTestClient]:
    """Real app wired to the savepoint `db_session` + the injected-key config.

    Overrides the `db_session` DI provider so `provide_transaction` runs against
    the test's savepoint session (nested begin -> savepoint; outer never commits ->
    rolls back at teardown). The magic-link route's `dispatch_task` is patched to a
    counting fake so the QUEUED email is asserted via the persisted Message row
    without invoking the SEND_EMAIL task (which needs `email_client` ctx).
    """
    sent_emails: list[dict[str, Any]] = []

    async def _fake_dispatch(transaction, request, task_name, *, queue="default", **kwargs):
        if task_name == TaskName.SEND_EMAIL:
            sent_emails.append(kwargs)

    monkeypatch.setattr("app.platform.comms.service.emails.dispatch_task", _fake_dispatch)

    # Request-scoped transaction on the savepoint session — mirrors the production
    # `provide_transaction` (app/utils/deps.py) under the non-superuser role model:
    # the connection is the NON-superuser `pear_app` role (no `SET ROLE`), and for
    # an authenticated request we set `app.user_id` + pin the escape OFF.
    #
    # Unauthenticated login routes (otp/check, apple, magic-link) set no
    # `app.user_id`; their first-login `profiles` INSERT succeeds because
    # `AuthService.find_or_create_identity` turns on the honored
    # `app.is_system_mode` escape itself — a genuine bypass, NOT a superuser
    # connection. That is the bootstrap behavior this suite exercises end-to-end.
    async def _test_transaction(request: Request) -> AsyncGenerator[AsyncSession]:
        # Switch the RLS actor in place on the shared savepoint session, then RESTORE
        # system mode on exit so the next request/assertion (and fixture seeding) is
        # unaffected. `SET LOCAL` is transaction-scoped (it survives savepoints), so
        # explicit restore (not savepoint rollback) is what keeps requests isolated.
        async with db_session.begin_nested():
            principal = request.scope.get("user")
            await db_session.execute(text("SET LOCAL app.is_system_mode = false"))
            if principal is not None:
                # Authenticated request (/me, /logout): scope to the verified user.
                await db_session.execute(text(f"SET LOCAL app.user_id = '{principal.id}'"))
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
    )

    async with AsyncTestClient(app=app) as client:
        # Stash assertion handles on the client for the email/refresh tests.
        client.sent_emails = sent_emails  # type: ignore[attr-defined]
        client.db_session = db_session  # type: ignore[attr-defined]
        client.config = auth_config  # type: ignore[attr-defined]
        yield client


# ── Small request helpers ──────────────────────────────────────────────────────


async def _otp_login(client: AsyncTestClient, phone: str, code: str | None = None) -> Any:
    code = code if code is not None else client.config.DEV_OTP_CODE  # type: ignore[attr-defined]
    return await client.post("/auth/otp/check", json={"phone": phone, "code": code})


def _auth_header(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


# ── OTP ────────────────────────────────────────────────────────────────────────


async def test_otp_start_returns_204(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.post("/auth/otp/start", json={"phone": "+15551230001"})
    assert resp.status_code == 204


async def test_otp_check_happy_path_creates_profile_and_identity(auth_app: AsyncTestClient) -> None:
    phone = "+15551230002"
    resp = await _otp_login(auth_app, phone)
    assert resp.status_code == 201, resp.text

    body = resp.json()
    assert body["accessToken"] and body["refreshToken"]
    assert body["user"]["id"]
    # A bootstrap profile carries the model's NOT-NULL server default role ('dater');
    # onboarding may later switch it to 'winger'.
    assert body["user"]["role"] == "dater"

    # The access token is a real ES256 JWT whose sub == the new profile id.
    claims = TokenService(db=None, config=auth_app.config).verify_access_token(body["accessToken"])  # type: ignore[arg-type,attr-defined]
    assert claims["sub"] == body["user"]["id"]

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    # A phone identity row was bootstrapped with the E.164 subject.
    identity = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.PHONE,
                AuthIdentity.provider_subject == phone,
            )
        )
    ).scalar_one()
    assert str(identity.profile_id) == body["user"]["id"]

    # A refresh token row was persisted as a SHA-256 hash (never the raw value).
    refresh_hash = hash_refresh_token(body["refreshToken"])
    row = (await db.execute(select(RefreshToken).where(RefreshToken.token_hash == refresh_hash))).scalar_one()
    assert row.revoked is False


async def test_otp_check_is_idempotent_for_same_phone(auth_app: AsyncTestClient) -> None:
    phone = "+15551230003"
    first = (await _otp_login(auth_app, phone)).json()
    second = (await _otp_login(auth_app, phone)).json()
    # Same phone -> same profile (find-or-create), distinct refresh tokens.
    assert first["user"]["id"] == second["user"]["id"]
    assert first["refreshToken"] != second["refreshToken"]


async def test_otp_check_wrong_code_rejected(auth_app: AsyncTestClient) -> None:
    resp = await _otp_login(auth_app, "+15551230004", code="111111")
    assert resp.status_code == 401
    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    # No identity created on a failed verification.
    count = (
        await db.execute(
            select(func.count()).select_from(AuthIdentity).where(AuthIdentity.provider_subject == "+15551230004")
        )
    ).scalar_one()
    assert count == 0


async def test_otp_start_rate_limited_after_budget(auth_app: AsyncTestClient) -> None:
    phone = "+15551230005"
    # Default in-memory limiter budget is 5 per window.
    statuses = [(await auth_app.post("/auth/otp/start", json={"phone": phone})).status_code for _ in range(5)]
    assert statuses == [204, 204, 204, 204, 204]
    over = await auth_app.post("/auth/otp/start", json={"phone": phone})
    assert over.status_code == 429


# ── Apple ──────────────────────────────────────────────────────────────────────


async def test_apple_valid_token_creates_session(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: TestConfig = auth_app.config  # type: ignore[attr-defined]
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
    body = resp.json()
    assert body["accessToken"] and body["refreshToken"]
    # `fullName` lands on the bootstrap profile as chosen_name.
    assert body["user"]["chosenName"] == "Ada Lovelace"

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    identity = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.APPLE,
                AuthIdentity.provider_subject == "apple-user-1",
            )
        )
    ).scalar_one()
    assert str(identity.profile_id) == body["user"]["id"]


async def test_apple_same_subject_returns_same_profile(
    auth_app: AsyncTestClient, apple_keypair: tuple[str, str]
) -> None:
    private_pem, _ = apple_keypair
    cfg: TestConfig = auth_app.config  # type: ignore[attr-defined]

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
    assert first["user"]["id"] == second["user"]["id"]


async def test_apple_wrong_aud_rejected(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: TestConfig = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(private_pem, aud="someone.else", iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=5))
    resp = await auth_app.post("/auth/apple", json={"identityToken": token})
    assert resp.status_code == 401


async def test_apple_expired_rejected(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: TestConfig = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(private_pem, aud=cfg.APPLE_CLIENT_ID, iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=-5))
    resp = await auth_app.post("/auth/apple", json={"identityToken": token})
    assert resp.status_code == 401


async def test_apple_tampered_signature_rejected(auth_app: AsyncTestClient, apple_keypair: tuple[str, str]) -> None:
    private_pem, _ = apple_keypair
    cfg: TestConfig = auth_app.config  # type: ignore[attr-defined]
    token = _apple_token(private_pem, aud=cfg.APPLE_CLIENT_ID, iss=cfg.APPLE_ISSUER, exp_delta=timedelta(minutes=5))
    tampered = token[:-4] + ("aaaa" if not token.endswith("aaaa") else "bbbb")
    resp = await auth_app.post("/auth/apple", json={"identityToken": tampered})
    assert resp.status_code == 401


# ── Magic link ─────────────────────────────────────────────────────────────────


def _magic_store(client: AsyncTestClient) -> InMemoryMagicLinkStore:
    """Reach into the per-config memoized in-memory store to read the minted token."""
    store = _magic_link_store_for(client.config)  # type: ignore[attr-defined]
    assert isinstance(store, InMemoryMagicLinkStore)
    return store


def _token_for_email(store: InMemoryMagicLinkStore, email: str) -> str:
    for token, (bound_email, _exp) in store._tokens.items():  # type: ignore[attr-defined]
        if bound_email == email:
            return token
    raise AssertionError(f"no magic-link token minted for {email}")


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


async def test_magic_link_verify_once_then_replay_rejected(auth_app: AsyncTestClient) -> None:
    email = "ml-verify@example.com"
    await auth_app.post("/auth/magic-link/request", json={"email": email})
    token = _token_for_email(_magic_store(auth_app), email)

    # First verify succeeds and issues a session for the email identity.
    first = await auth_app.post("/auth/magic-link/verify", json={"token": token})
    assert first.status_code == 201, first.text
    body = first.json()
    assert body["accessToken"] and body["refreshToken"]

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    identity = (
        await db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == AuthProvider.EMAIL,
                AuthIdentity.provider_subject == email,
            )
        )
    ).scalar_one()
    assert str(identity.profile_id) == body["user"]["id"]

    # Replay of the consumed token is rejected.
    replay = await auth_app.post("/auth/magic-link/verify", json={"token": token})
    assert replay.status_code == 401


async def test_magic_link_expired_token_rejected(auth_app: AsyncTestClient) -> None:
    email = "ml-expired@example.com"
    await auth_app.post("/auth/magic-link/request", json={"email": email})
    store = _magic_store(auth_app)
    token = _token_for_email(store, email)
    # Force the entry's expiry into the past.
    bound_email, _ = store._tokens[token]  # type: ignore[attr-defined]
    store._tokens[token] = (bound_email, time.time() - 1)  # type: ignore[attr-defined]

    resp = await auth_app.post("/auth/magic-link/verify", json={"token": token})
    assert resp.status_code == 401


async def test_magic_link_verify_redirect_hops_into_app_scheme(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.get(
        "/auth/magic-link/verify",
        params={"token": "some-token"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert resp.headers["location"] == "pear://magic-link?token=some-token"


# ── Refresh rotation + reuse detection ─────────────────────────────────────────


async def test_refresh_rotates_pair_and_revokes_old(auth_app: AsyncTestClient) -> None:
    login = (await _otp_login(auth_app, "+15551230010")).json()
    old_refresh = login["refreshToken"]

    rotated = await auth_app.post("/auth/refresh", json={"refreshToken": old_refresh})
    assert rotated.status_code == 200, rotated.text
    pair = rotated.json()
    assert pair["accessToken"] and pair["refreshToken"]
    assert pair["refreshToken"] != old_refresh

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    old_row = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(old_refresh)))
    ).scalar_one()
    assert old_row.revoked is True
    # The old token points at its replacement (the rotation chain link).
    new_row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(pair["refreshToken"]))
        )
    ).scalar_one()
    assert old_row.replaced_by == new_row.id
    assert new_row.revoked is False

    # The new refresh token works.
    again = await auth_app.post("/auth/refresh", json={"refreshToken": pair["refreshToken"]})
    assert again.status_code == 200


async def test_refresh_reuse_detection_revokes_chain(auth_app: AsyncTestClient) -> None:
    login = (await _otp_login(auth_app, "+15551230011")).json()
    refresh_1 = login["refreshToken"]

    # Rotate once: refresh_1 -> refresh_2 (refresh_1 now revoked).
    pair = (await auth_app.post("/auth/refresh", json={"refreshToken": refresh_1})).json()
    refresh_2 = pair["refreshToken"]

    # Reusing the already-rotated refresh_1 is reuse detection: rejected with 401.
    reuse = await auth_app.post("/auth/refresh", json={"refreshToken": refresh_1})
    assert reuse.status_code == 401

    # The whole chain is burned — refresh_2 (the active child) is now revoked too.
    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    row_2 = (
        await db.execute(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(refresh_2)))
    ).scalar_one()
    assert row_2.revoked is True
    # And refresh_2 can no longer be rotated.
    after = await auth_app.post("/auth/refresh", json={"refreshToken": refresh_2})
    assert after.status_code == 401


async def test_refresh_unknown_token_rejected(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.post("/auth/refresh", json={"refreshToken": "not-a-real-token"})
    assert resp.status_code == 401


# ── Access token + /auth/me + logout ───────────────────────────────────────────


async def test_me_with_valid_token_returns_user(auth_app: AsyncTestClient) -> None:
    login = (await _otp_login(auth_app, "+15551230020")).json()
    resp = await auth_app.get("/auth/me", headers=_auth_header(login["accessToken"]))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["user"]["id"] == login["user"]["id"]


async def test_me_without_token_rejected(auth_app: AsyncTestClient) -> None:
    resp = await auth_app.get("/auth/me")
    assert resp.status_code in (401, 403)


async def test_me_with_expired_access_token_rejected(auth_app: AsyncTestClient) -> None:
    cfg: TestConfig = auth_app.config  # type: ignore[attr-defined]
    # Mint an already-expired access token signed with the app's real JWT key.
    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": "00000000-0000-0000-0000-000000000001",
            "role": None,
            "iat": int((now - timedelta(hours=1)).timestamp()),
            "exp": int((now - timedelta(minutes=30)).timestamp()),
            "iss": cfg.JWT_ISSUER,
            "aud": cfg.JWT_AUDIENCE,
        },
        cfg.JWT_SIGNING_KEY,
        algorithm="ES256",
    )
    resp = await auth_app.get("/auth/me", headers=_auth_header(expired))
    assert resp.status_code in (401, 403)


async def test_me_with_tampered_access_token_rejected(auth_app: AsyncTestClient) -> None:
    login = (await _otp_login(auth_app, "+15551230021")).json()
    tampered = login["accessToken"][:-4] + ("aaaa" if not login["accessToken"].endswith("aaaa") else "bbbb")
    resp = await auth_app.get("/auth/me", headers=_auth_header(tampered))
    assert resp.status_code in (401, 403)


async def test_logout_revokes_refresh_token(auth_app: AsyncTestClient) -> None:
    login = (await _otp_login(auth_app, "+15551230022")).json()

    resp = await auth_app.post(
        "/auth/logout",
        json={"refreshToken": login["refreshToken"]},
        headers=_auth_header(login["accessToken"]),
    )
    assert resp.status_code == 204

    db: AsyncSession = auth_app.db_session  # type: ignore[attr-defined]
    row = (
        await db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(login["refreshToken"]))
        )
    ).scalar_one()
    assert row.revoked is True

    # A revoked refresh token can no longer be rotated (reuse detection -> 401).
    after = await auth_app.post("/auth/refresh", json={"refreshToken": login["refreshToken"]})
    assert after.status_code == 401


async def test_logout_requires_access_token(auth_app: AsyncTestClient) -> None:
    login = (await _otp_login(auth_app, "+15551230023")).json()
    resp = await auth_app.post("/auth/logout", json={"refreshToken": login["refreshToken"]})
    assert resp.status_code in (401, 403)
