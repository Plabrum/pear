from typing import Any

from litestar import Request
from litestar.exceptions import NotAuthorizedException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.platform.auth.clients.apple import BaseAppleVerifier, build_apple_verifier
from app.platform.auth.clients.apple_oauth import BaseAppleOAuthClient, build_apple_oauth_client
from app.platform.auth.principal import User
from app.platform.auth.service import AuthService
from app.utils.deps import dep


@dep("user", sync_to_thread=False)
def provide_current_user(request: Request[User | None, Any, Any]) -> User:
    """Inject the authenticated principal as `user`.

    SessionAuth's middleware loads the principal via `retrieve_user_handler` and sets
    it on `request.user`; this `@dep("user")` binding is what exposes it to handlers
    and actions under the name `user`. Routes that allow anonymous access must not
    depend on `user`.
    """
    if request.user is None:
        raise NotAuthorizedException()
    return request.user


@dep("auth_service", sync_to_thread=False)
def provide_auth_service(transaction: AsyncSession) -> AuthService:
    return AuthService(db=transaction, config=config)


@dep("apple_verifier", sync_to_thread=False)
def provide_apple_verifier() -> BaseAppleVerifier:
    """Apple identity-token verifier: injected-key in test, JWKS in prod."""
    return build_apple_verifier(config)


# Memoized like the push client so the real client's cached client_secret JWT
# survives across requests — DI providers are otherwise per-request.
_apple_oauth_clients: dict[int, BaseAppleOAuthClient] = {}


@dep("apple_oauth_client", sync_to_thread=False)
def provide_apple_oauth_client() -> BaseAppleOAuthClient:
    """Outbound Apple OAuth client (code exchange + grant revoke): local in dev/test, real in prod."""
    client = _apple_oauth_clients.get(id(config))
    if client is None:
        client = build_apple_oauth_client(config)
        _apple_oauth_clients[id(config)] = client
    return client


@dep("email", sync_to_thread=False)
def provide_email(email_service: Any) -> Any:
    """Alias of the comms `email_service` under the name the actions layer uses."""
    return email_service


@dep("state_machine_service", sync_to_thread=False)
def provide_state_machine_service(sm_service: Any) -> Any:
    """Alias of the state-machine `sm_service` under the actions-layer name."""
    return sm_service
