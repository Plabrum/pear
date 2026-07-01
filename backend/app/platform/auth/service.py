"""AuthService — identity bootstrap + session issuance.

This is the shared core the login-method routes (OTP / Apple / magic link) call
after they have verified an external credential and resolved a stable subject:

  * `find_or_create_identity(provider, subject, *, email?, name?)` — resolves an
    `auth_identities` row to a profile, creating both the profile (first-login
    bootstrap — replaces the old Supabase `on_auth_user_created` trigger) and the
    identity row when absent. Returns `(profile, created)`.
  * `issue_session(profile, *, device_info?)` — mints an access+refresh pair and
    returns the `{accessToken, refreshToken, user}` payload.

**RLS bootstrap:** the login-method routes are *unauthenticated* — no
`app.user_id` is set, so RLS would fail closed on the `profiles` /
`auth_identities` inserts. AuthService therefore runs its identity work in
**system mode** (`SET LOCAL app.is_system_mode = true`), the same escape hatch the
test fixtures use. The session is the request transaction; system mode is scoped
to it and rolls back / commits with the request.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity
from app.platform.auth.principal import User
from app.platform.auth.schemas import SessionOut, user_out_from_principal
from app.platform.auth.tokens import TokenService


class AuthService:
    def __init__(self, db: AsyncSession, config: Config, tokens: TokenService):
        self.db = db
        self.config = config
        self.tokens = tokens

    async def _enter_system_mode(self) -> None:
        """Bypass RLS for identity bootstrap (auth runs before a user exists)."""
        await self.db.execute(text("SET LOCAL app.is_system_mode = true"))

    async def find_or_create_identity(
        self,
        provider: AuthProvider,
        subject: str,
        *,
        email: str | None = None,
        name: str | None = None,
    ) -> tuple[Profile, bool]:
        """Resolve (provider, subject) to a profile, bootstrapping on first login.

        `email`/`name` are persisted onto the profile only when creating it (Apple
        delivers them once, on first authorization). Returns `(profile, created)`.
        """
        await self._enter_system_mode()

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
                profile = await self._create_profile(provider, subject, email=email, name=name)
                identity.profile_id = profile.id
                await self.db.flush()
                return profile, True
            return profile, False

        profile = await self._create_profile(provider, subject, email=email, name=name)
        identity = AuthIdentity(provider=provider, provider_subject=subject, profile_id=profile.id)
        self.db.add(identity)
        await self.db.flush()
        return profile, True

    async def _create_profile(
        self,
        provider: AuthProvider,
        subject: str,
        *,
        email: str | None = None,
        name: str | None = None,
    ) -> Profile:
        """Create a bootstrap profile row. Onboarding fills in role/chosen_name."""
        profile = Profile()
        if provider is AuthProvider.PHONE:
            profile.phone_number = subject
        if name:
            profile.chosen_name = name
        # `email` is recorded via the email identity row's subject; only stash the
        # name here (profiles has no email column — that is the identity's subject).
        self.db.add(profile)
        await self.db.flush()
        return profile

    def _user_payload(self, profile: Profile) -> User:
        return User.from_profile(profile)

    async def issue_session(self, profile: Profile, *, device_info: str | None = None) -> SessionOut:
        """Mint an access+refresh pair and assemble the session payload."""
        await self._enter_system_mode()
        access = self.tokens.issue_access_token(profile)
        refresh = await self.tokens.mint_refresh_token(profile.id, device_info=device_info)
        return SessionOut(
            access_token=access,
            refresh_token=refresh,
            user=user_out_from_principal(self._user_payload(profile)),
        )

    async def load_profile(self, profile_id: UUID) -> Profile | None:
        """Load a profile by id (used by the middleware after token verification)."""
        return await self.db.get(Profile, profile_id)

    @staticmethod
    def profile_role_value(profile: Profile) -> str | None:
        return profile.role.value if isinstance(profile.role, UserRole) else None
