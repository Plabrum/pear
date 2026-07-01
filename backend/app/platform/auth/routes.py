from __future__ import annotations

from litestar import Request, Router, get, post

from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.auth.routes_methods import LOGIN_METHOD_ROUTES
from app.platform.auth.schemas import MeOut, user_out_from_principal
from app.platform.auth.service import AuthService


@post("/logout", status_code=204, guards=[requires_session])
async def logout(request: Request) -> None:
    """Clear the cookie session. Requires an authenticated session."""
    request.clear_session()


@get("/me", guards=[requires_session])
async def me(user: User) -> MeOut:
    """Return the authenticated user. Requires a cookie session."""
    return MeOut(user=user_out_from_principal(user))


# Re-export so the factory can reference the assembled service.
__all__ = ["AuthService", "auth_router"]

auth_router = Router(
    path="/auth",
    route_handlers=[logout, me, *LOGIN_METHOD_ROUTES],
    tags=["auth"],
)
