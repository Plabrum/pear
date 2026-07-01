from __future__ import annotations

from litestar import Request, Router, get, post
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.models import DatingProfile
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
async def me(user: User, transaction: AsyncSession) -> MeOut:
    """Return the authenticated user + whether they have a dating profile.

    The existence check is a cheap self-select on the user's own row, permitted
    under their RLS scope (same access `getApiDatingProfilesMe` already grants).
    It feeds the routing gate so the client needs only this one session query.
    """
    result = await transaction.execute(select(DatingProfile.id).where(DatingProfile.user_id == user.id).limit(1))
    has_dating_profile = result.scalar_one_or_none() is not None
    return MeOut(user=user_out_from_principal(user), has_dating_profile=has_dating_profile)


# Re-export so the factory can reference the assembled service.
__all__ = ["AuthService", "auth_router"]

auth_router = Router(
    path="/auth",
    route_handlers=[logout, me, *LOGIN_METHOD_ROUTES],
    tags=["auth"],
)
