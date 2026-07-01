from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.

# Tables intentionally WITHOUT row-level security. Every entry must justify why no
# row scoping applies; a NEW table that lacks both FORCE RLS and an entry here fails
# the coverage test below (that gap is exactly what let tables ship unprotected).
#
# RLS cannot be added to these without breaking writes: they are written on
# unauthenticated/system paths with no clean owner column, and have no user-facing
# read to scope.
_INTENTIONAL_NO_RLS = {
    "alembic_version",  # Alembic migration bookkeeping — no user data.
    "tasks",  # Background-job queue — system/worker writes only, never user-read.
    "profiles",  # Root identity table: world-readable, scoped at the app layer. A
    # row's scope is unknowable before its id exists (the unauthenticated first-login
    # bootstrap would have to "become" a user before that user exists).
    "auth_identities",  # External-login lookup rows: written unauthenticated on first
    # login, no clean owner column, never user-read.
    # LOUD: `email_messages` stores magic-link email BODIES (which contain tokens). It
    # is safe today ONLY because nothing reads it — any future read path MUST be
    # actor-scoped (RLS or app layer) before it is added, or it leaks bearer secrets.
    "email_messages",
    "events",  # Append-only lifecycle log: system-written, read only via scoped feeds.
    "state_transition_logs",  # Append-only state-machine audit log: system-written.
    "app_updates",  # OTA manifest rows: written by the unauthenticated (bearer-token
    # guarded) `POST /updates/publish` CI endpoint, read by the unauthenticated
    # `GET /updates/manifest` route — no per-request actor either way, same shape as
    # `profiles`.
    "native_build_fingerprints",  # Same shape as `app_updates`: written by the
    # bearer-token-guarded `POST /updates/native-build-fingerprint` (Xcode Cloud CI),
    # read by the unauthenticated `GET /updates/native-build-fingerprint` — no
    # per-request actor either way.
}


async def test_every_table_has_rls_or_is_allowlisted(db_session: AsyncSession) -> None:
    """Every `public` table is FORCE RLS or explicitly allowlisted — no silent gaps.

    The drift net: a new table that ships with neither FORCE ROW LEVEL SECURITY nor
    an `_INTENTIONAL_NO_RLS` entry fails here. Declare RLS on the model via
    `RLSScopedMixin`, or allowlist the table with a one-line rationale.
    """
    rows = (
        await db_session.execute(
            text(
                """
                SELECT c.relname, c.relforcerowsecurity
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                WHERE n.nspname = 'public' AND c.relkind = 'r'
                """
            )
        )
    ).all()

    missing = sorted(
        name
        for name, force_rls in rows
        # `saq_*` are SAQ's own runtime tables (excluded from migrations in env.py).
        if not force_rls and name not in _INTENTIONAL_NO_RLS and not name.startswith("saq_")
    )

    assert not missing, (
        f"Tables shipped with neither FORCE RLS nor an _INTENTIONAL_NO_RLS entry: {missing}. "
        "Declare RLS on the model via RLSScopedMixin, or allowlist the table here with a rationale."
    )
