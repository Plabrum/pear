"""Auth guards.

`requires_session` is the single guard used in this phase (e.g. on the actions
router). It asserts that the STUB auth middleware resolved a principal onto the
connection. `requires_local` gates dev-only endpoints.

TODO(Phase 4): add real role guards (`requires_role`) once the users domain and
verified tokens exist.
"""

from litestar.connection import ASGIConnection
from litestar.exceptions import NotAuthorizedException
from litestar.handlers.base import BaseRouteHandler

from app.config import config


def requires_session(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard: require an authenticated principal on the connection."""
    if not connection.user:
        raise NotAuthorizedException("Authentication required")


def requires_local(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard: only allow the request in development or test environments."""
    if not config.IS_DEV and config.ENV != "testing":
        raise NotAuthorizedException("This endpoint is only available in development mode")
