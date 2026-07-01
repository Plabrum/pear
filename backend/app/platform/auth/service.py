from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity, MagicLinkToken


class AuthService:
    def __init__(self, db: AsyncSession, config: Config):
        self.db = db
        self.config = config

    # ── Magic-link tokens ─────────────────────────────────────────────────────

    def _hash_token(self, token: str) -> str:
        """HMAC-SHA256 the raw token with `SECRET_KEY` (hex digest, 64 chars).

        Keyed (not a bare hash) so a DB leak of `token_hash` can't be brute-forced
        into a usable token without also holding the server secret.
        """
        return hmac.new(self.config.SECRET_KEY.encode(), token.encode(), hashlib.sha256).hexdigest()

    async def issue_magic_link(self, email: str) -> str:
        """Mint a single-use token bound to `email`, persist its hash, return the raw token.

        The raw token is returned to the caller exactly once (to put in the emailed
        link) and never stored — only its `_hash_token` lands in `magic_link_tokens`.
        """
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(seconds=self.config.MAGIC_LINK_TTL_SECONDS)
        self.db.add(MagicLinkToken(token_hash=self._hash_token(token), email=email, expires_at=expires_at))
        await self.db.flush()
        return token

    async def consume_magic_link(self, token: str) -> str | None:
        """Atomically consume a token: return its email once, then never again.

        Returns `None` for unknown / already-consumed / expired tokens (replay and
        expiry both fail the same way — the caller maps that to a 401). The row is
        locked `FOR UPDATE` so a concurrent double-submit serializes to one winner.
        """
        result = await self.db.execute(
            select(MagicLinkToken)
            .where(
                MagicLinkToken.token_hash == self._hash_token(token),
                MagicLinkToken.used_at.is_(None),
                MagicLinkToken.expires_at > datetime.now(UTC),
            )
            .with_for_update()
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.used_at = datetime.now(UTC)
        await self.db.flush()
        return row.email

    async def find_or_create_identity(
        self,
        provider: AuthProvider,
        subject: str,
        *,
        email: str | None = None,
        name: str | None = None,
    ) -> tuple[Profile, bool]:
        """Resolve (provider, subject) to a profile, bootstrapping on first login.

        `name` is persisted onto the profile only when creating it (Apple delivers
        it once, on first authorization). Returns `(profile, created)`.

        Runs on the unauthenticated bootstrap path with no actor yet set. Identity
        lookups touch `auth_identities` and `profiles`, neither of which carries RLS,
        and the profile INSERT is likewise unguarded at the DB — so no actor scoping
        or system-mode escape is needed here.
        """
        result = await self.db.execute(
            select(AuthIdentity).where(
                AuthIdentity.provider == provider,
                AuthIdentity.provider_subject == subject,
            )
        )
        identity = result.scalar_one_or_none()
        if identity is not None:
            profile = await self.db.get(Profile, identity.profile_id)
            if profile is None:
                # Identity orphaned (profile soft-deleted/gone) — recreate a profile.
                profile = await self._create_profile(name=name)
                identity.profile_id = profile.id
                await self.db.flush()
                return profile, True
            return profile, False

        profile = await self._create_profile(name=name)
        identity = AuthIdentity(provider=provider, provider_subject=subject, profile_id=profile.id)
        self.db.add(identity)
        await self.db.flush()
        return profile, True

    async def _create_profile(self, *, name: str | None = None) -> Profile:
        """Create a bootstrap profile row. Onboarding fills in role/chosen_name.

        The `profiles` identity table carries no RLS (see `_INTENTIONAL_NO_RLS` in
        `tests/test_rls_coverage.py`),
        so the unauthenticated first-login bootstrap just inserts the row — no actor
        scoping or system-mode escape needed. The id is assigned by the serial PK and
        comes back through `SqidType`'s result processor, so `profile.id` is a `Sqid`
        (serialises to its sqid string in the login response, matching the /me path).
        """
        profile = Profile()
        if name:
            profile.chosen_name = name
        # An email login records its address as the identity row's subject; the
        # profile has no email column, so only the optional name is stashed here.
        self.db.add(profile)
        await self.db.flush()
        return profile

    async def load_profile(self, profile_id: int) -> Profile | None:
        """Load a profile by id."""
        return await self.db.get(Profile, profile_id)

    @staticmethod
    def profile_role_value(profile: Profile) -> str | None:
        return profile.state.value if isinstance(profile.state, UserRole) else None
