from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config
from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.auth.enums import AuthProvider
from app.platform.auth.models import AuthIdentity
from app.platform.auth.principal import User
from app.platform.auth.schemas import SessionOut, user_out_from_principal
from app.platform.auth.tokens import TokenService
from app.utils.deps import set_request_user


class AuthService:
    def __init__(self, db: AsyncSession, config: Config, tokens: TokenService):
        self.db = db
        self.config = config
        self.tokens = tokens

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
        lookups touch `auth_identities` (no RLS) and `profiles` (public select), so
        no escape is needed; the only RLS-gated write is the profile INSERT, which
        `_create_profile` scopes to the new profile's own id (id = current_user_id()).
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

        The bootstrap acts AS the new user, not as a system actor: we generate the
        profile's id up front and pin `app.user_id` to it so the `profiles_insert`
        WITH CHECK (`id = current_user_id()`) is satisfied under the user's OWN
        scope. `SET LOCAL` is transaction-scoped, so it cannot leak across requests.
        """
        new_id = uuid4()
        await set_request_user(self.db, new_id)
        profile = Profile(id=new_id)
        if name:
            profile.chosen_name = name
        # An email login records its address as the identity row's subject; the
        # profile has no email column, so only the optional name is stashed here.
        self.db.add(profile)
        await self.db.flush()
        return profile

    def _user_payload(self, profile: Profile) -> User:
        return User.from_profile(profile)

    async def issue_session(self, profile: Profile, *, device_info: str | None = None) -> SessionOut:
        """Mint an access+refresh pair and assemble the session payload.

        `refresh_tokens` has no RLS, so minting needs no escape; the access token is
        stateless. No system mode in the auth request path.
        """
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
