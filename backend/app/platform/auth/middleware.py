"""ES256 bearer authentication middleware (Phase 4 — REAL verification).

Replaces the Phase-2 decode-only stub. Extracts the `Bearer <jwt>` access token,
**verifies its ES256 signature + exp + iss/aud** via `TokenService`, and attaches a
verified principal (`VerifiedPrincipal`: the token `sub` as UUID + the `role`
claim) to `connection.scope["user"]`. Downstream:

  * `provide_transaction` reads `request.user.id` — now a *verified* uuid — to
    `SET LOCAL app.user_id` (the RLS GUC). Unverified/absent token => no
    principal => no `app.user_id` => RLS fails closed.
  * `provide_current_user` (`@dep("user")`) loads the full `Profile` under the
    RLS-scoped transaction and builds the rich `User` (id + role + chosen_name).
  * `requires_session` asserts a principal is present.

ASGI middleware runs before DI, so it does **no DB work** — it only proves the
token is authentic and hands the verified id forward. The unauthenticated
`/auth/*` routes plus `^/health` and `^/schema` are excluded (see factory.py).
Requests with no / malformed / invalid token are left unauthenticated
(`user=None`); guards decide whether anonymous access is allowed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from litestar.connection import ASGIConnection
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult

from app.config import Config, config
from app.domain.profiles.enums import UserRole
from app.platform.auth.tokens import TokenError, TokenService
from app.platform.state_machine.roles import Role

logger = logging.getLogger(__name__)


@dataclass
class VerifiedPrincipal:
    """Minimal principal proven by a verified access token.

    Carries the verified `sub` (uuid) used by `provide_transaction` to set the
    RLS GUC, plus the advisory `role` claim. The full DB-backed `User` is built
    later by `provide_current_user`. Satisfies the `Actor` protocol (`.id`/`.role`).
    """

    id: UUID
    role: Role = Role.DATER


def _principal_from_claims(claims: dict) -> VerifiedPrincipal | None:
    sub = claims.get("sub")
    if not sub:
        return None
    try:
        user_id = UUID(str(sub))
    except (ValueError, AttributeError):
        return None
    raw_role = claims.get("role")
    # `role` claim holds the profile's dater|winger value; map to a transition Role.
    role = Role.DATER
    if raw_role is not None:
        try:
            role = Role.WINGER if UserRole(raw_role) is UserRole.WINGER else Role.DATER
        except ValueError:
            role = Role.DATER
    return VerifiedPrincipal(id=user_id, role=role)


class JWTAuthMiddleware(AbstractAuthenticationMiddleware):
    """Verify the Bearer access token's ES256 signature and attach the principal."""

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        auth_header = connection.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")

        principal: VerifiedPrincipal | None = None
        if scheme.lower() == "bearer" and token:
            # Use the app's active config (shared via state) so verification uses the
            # SAME keypair that signed the token. Falls back to the module singleton.
            active_config: Config = getattr(connection.app.state, "config", None) or config
            # TokenService is stateless for verification (no DB needed); pass None
            # as the session — verify_access_token never touches it.
            service = TokenService(db=None, config=active_config)  # type: ignore[arg-type]
            try:
                claims = service.verify_access_token(token)
            except TokenError:
                claims = None
            if claims is not None:
                principal = _principal_from_claims(claims)

        return AuthenticationResult(user=principal, auth=token or None)
