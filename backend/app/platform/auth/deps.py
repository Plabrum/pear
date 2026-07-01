from typing import Any

from litestar import Request
from litestar.exceptions import NotAuthorizedException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config, config
from app.domain.profiles.models import Profile
from app.platform.auth.clients.apple import BaseAppleVerifier, build_apple_verifier
from app.platform.auth.magic_link import BaseMagicLinkStore, build_magic_link_store
from app.platform.auth.principal import User
from app.platform.auth.rate_limit import BaseRateLimiter, build_rate_limiter
from app.platform.auth.service import AuthService
from app.platform.auth.tokens import TokenService
from app.utils.deps import dep

# Process-level caches. Both the magic-link store and the rate limiter hold state
# that MUST outlive a single request (a minted token must survive to be consumed;
# a counter must accumulate across requests). DI providers are per-request, so we
# memoize one instance per config object.
_magic_link_stores: dict[int, BaseMagicLinkStore] = {}
_rate_limiters: dict[int, BaseRateLimiter] = {}


def _magic_link_store_for(cfg: Config) -> BaseMagicLinkStore:
    store = _magic_link_stores.get(id(cfg))
    if store is None:
        store = build_magic_link_store(cfg)
        _magic_link_stores[id(cfg)] = store
    return store


def _rate_limiter_for(cfg: Config) -> BaseRateLimiter:
    limiter = _rate_limiters.get(id(cfg))
    if limiter is None:
        limiter = build_rate_limiter(cfg)
        _rate_limiters[id(cfg)] = limiter
    return limiter


def _active_config(request: Request) -> Config:
    """The app's active config (shared via state) — the keypair authority.

    Token sign + verify must use the same config instance; in tests that is the
    ephemeral-keypair `TestConfig` passed to `create_app`. Falls back to the
    module singleton (prod, where every config is built from the same env PEM).
    """
    return getattr(request.app.state, "config", None) or config


@dep("token_service", sync_to_thread=False)
def provide_token_service(transaction: AsyncSession, request: Request) -> TokenService:
    return TokenService(db=transaction, config=_active_config(request))


@dep("auth_service", sync_to_thread=False)
def provide_auth_service(transaction: AsyncSession, request: Request, token_service: TokenService) -> AuthService:
    return AuthService(db=transaction, config=_active_config(request), tokens=token_service)


@dep("apple_verifier", sync_to_thread=False)
def provide_apple_verifier(request: Request) -> BaseAppleVerifier:
    """Apple identity-token verifier: injected-key in test, JWKS in prod."""
    return build_apple_verifier(_active_config(request))


@dep("magic_link_store", sync_to_thread=False)
def provide_magic_link_store(request: Request) -> BaseMagicLinkStore:
    """Single-use magic-link token store: in-memory in dev/test, Redis in prod.

    Memoized per config so the token minted on `/magic-link/request` survives to be
    consumed on `/magic-link/verify` (DI is otherwise per-request).
    """
    return _magic_link_store_for(_active_config(request))


@dep("rate_limiter", sync_to_thread=False)
def provide_rate_limiter(request: Request) -> BaseRateLimiter:
    """Fixed-window rate limiter for magic-link/request.

    In-memory in dev/test, Redis in prod. Memoized per config so counts accumulate
    across requests.
    """
    return _rate_limiter_for(_active_config(request))


@dep("user")
async def provide_current_user(request: Request, transaction: AsyncSession) -> User:
    """Expose the authenticated principal to handlers and actions.

    The middleware has already verified the access token and placed a
    `VerifiedPrincipal` (verified `sub`) on the connection. Here we load the full
    profile under the RLS-scoped transaction and build the rich `User`. Routes
    that allow anonymous access must not depend on `user`.
    """
    principal = request.scope.get("user")
    if principal is None:
        raise NotAuthorizedException("Authentication required")

    profile = await transaction.get(Profile, principal.id)
    if profile is None:
        raise NotAuthorizedException("Authenticated profile no longer exists")
    return User.from_profile(profile)


@dep("email", sync_to_thread=False)
def provide_email(email_service: Any) -> Any:
    """Alias of the comms `email_service` under the name the actions layer uses."""
    return email_service


@dep("state_machine_service", sync_to_thread=False)
def provide_state_machine_service(sm_service: Any) -> Any:
    """Alias of the state-machine `sm_service` under the actions-layer name."""
    return sm_service
