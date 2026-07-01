"""Auth dependency providers (STUB).

Registers the request principal (`user`) plus the two DI-name aliases that
`app.platform.actions.deps.provide_action_deps` expects (`email`,
`state_machine_service`). The underlying services are owned by their platform
modules (comms `email_service`, state_machine `sm_service`); these thin aliases
exist only to match the names the actions layer resolves by, and will be
collapsed once those agents settle on final DI keys.

TODO(Phase 4): `provide_user` returns the STUB principal decoded from the JWT.
Replace with a DB-backed `User` load (with role) under the users domain.
"""

from typing import Any

from litestar import Request
from litestar.exceptions import NotAuthorizedException

from app.platform.auth.models import StubUser
from app.utils.deps import dep


@dep("user", sync_to_thread=False)
def provide_user(request: Request) -> StubUser:
    """Expose the authenticated principal to handlers and actions.

    Routes that allow anonymous access should not depend on `user`. Guarded
    routes (e.g. the actions router via `requires_session`) always have one.
    """
    user = request.scope.get("user")
    if user is None:
        raise NotAuthorizedException("Authentication required")
    return user


@dep("email", sync_to_thread=False)
def provide_email(email_service: Any) -> Any:
    """Alias of the comms `email_service` under the name the actions layer uses."""
    return email_service


@dep("state_machine_service", sync_to_thread=False)
def provide_state_machine_service(sm_service: Any) -> Any:
    """Alias of the state-machine `sm_service` under the actions-layer name."""
    return sm_service
