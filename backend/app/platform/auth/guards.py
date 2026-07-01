import hmac

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


def requires_updates_publish_token(connection: ASGIConnection, _: BaseRouteHandler) -> None:
    """Guard: bearer-token auth for the CI-only `POST /updates/publish` route.

    Not a user session — the caller is the `ota.yml` GitHub Actions job, which has
    no principal to authenticate as. Compared with `hmac.compare_digest` (constant
    time) to avoid a timing side-channel. An unset `UPDATES_PUBLISH_TOKEN` always
    rejects (fails closed), including against an empty-string presented token.
    """
    presented = connection.headers.get("authorization", "")
    expected = f"Bearer {config.UPDATES_PUBLISH_TOKEN}"
    if not config.UPDATES_PUBLISH_TOKEN or not hmac.compare_digest(presented, expected):
        raise NotAuthorizedException("Invalid or missing publish token")
