from __future__ import annotations

from litestar import Request, Response, Router, get, post

from app.platform.auth.guards import requires_session
from app.platform.auth.principal import User
from app.platform.auth.routes_methods import LOGIN_METHOD_ROUTES
from app.platform.auth.schemas import (
    LogoutIn,
    MeOut,
    RefreshIn,
    TokenPairOut,
    user_out_from_principal,
)
from app.platform.auth.service import AuthService
from app.platform.auth.tokens import TokenError, TokenService


def _device_info(request: Request) -> str | None:
    ua = request.headers.get("User-Agent")
    return ua[:512] if ua else None


@post("/refresh", exclude_from_auth=True)
async def refresh(
    data: RefreshIn, token_service: TokenService, request: Request
) -> Response[TokenPairOut] | Response[dict[str, str]]:
    """Rotate a refresh token into a fresh access+refresh pair.

    Returns a 401 *Response* (not a raise) on any failure so that the chain
    revocation performed by reuse detection commits with the request.
    """
    try:
        rotated = await token_service.rotate_refresh(data.refresh_token, device_info=_device_info(request))
    except TokenError as e:
        return Response(content={"detail": str(e)}, status_code=401)
    return Response(
        content=TokenPairOut(access_token=rotated.access_token, refresh_token=rotated.refresh_token),
        status_code=200,
    )


@post("/logout", status_code=204, guards=[requires_session])
async def logout(data: LogoutIn, token_service: TokenService) -> None:
    """Revoke the supplied refresh token. Requires a valid access token."""
    await token_service.revoke_refresh(data.refresh_token)


@get("/me", guards=[requires_session])
async def me(user: User) -> MeOut:
    """Return the authenticated user. Requires a valid access token."""
    return MeOut(user=user_out_from_principal(user))


# Re-export so the factory can reference the assembled service.
__all__ = ["AuthService", "auth_router"]

auth_router = Router(
    path="/auth",
    route_handlers=[refresh, logout, me, *LOGIN_METHOD_ROUTES],
    tags=["auth"],
)
