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
