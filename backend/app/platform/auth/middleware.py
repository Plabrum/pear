"""STUB JWT bearer authentication middleware.

Decodes (but does NOT verify) a `Bearer <jwt>` Authorization header and builds a
`StubUser` from the token's `sub` claim — exactly like the current Hono
`authMiddleware`, which trusts the gateway-issued token. The resulting principal
is attached to `connection.scope["user"]` and picked up by:

  * `provide_transaction` — sets the `app.user_id` RLS GUC from `request.user.id`
  * `provide_user` (`@dep("user")`) — exposes the principal to handlers/actions
  * `requires_session` — the guard on the actions router

Requests without a (decodable) token are left unauthenticated (`user=None`);
route guards decide whether that is allowed. `^/health` and `^/schema` are
excluded from this middleware entirely (see factory.py).

TODO(Phase 4): verify the ES256 signature against `config.JWT_PUBLIC_KEY`, check
`exp`/`aud`, and resolve the real `User` (with role) from the database.
"""

from __future__ import annotations

import base64
import binascii
import json
import logging
from uuid import UUID

from litestar.connection import ASGIConnection
from litestar.middleware import AbstractAuthenticationMiddleware, AuthenticationResult

from app.platform.auth.models import StubUser
from app.platform.state_machine.roles import Role

logger = logging.getLogger(__name__)


def _decode_jwt_unverified(token: str) -> dict | None:
    """Decode a JWT payload WITHOUT verifying its signature.

    Returns the decoded claims dict, or None if the token is malformed.

    WARNING: no signature/expiry verification — STUB only. See module docstring.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return None
    payload_b64 = parts[1]
    # JWT uses url-safe base64 without padding — re-pad before decoding.
    padding = "=" * (-len(payload_b64) % 4)
    try:
        raw = base64.urlsafe_b64decode(payload_b64 + padding)
        claims = json.loads(raw)
    except (binascii.Error, ValueError, json.JSONDecodeError):
        return None
    return claims if isinstance(claims, dict) else None


def _user_from_claims(claims: dict) -> StubUser | None:
    sub = claims.get("sub")
    if not sub:
        return None
    try:
        user_id = UUID(str(sub))
    except (ValueError, AttributeError):
        return None
    # `role` is advisory in this phase; default to dater when absent/unknown.
    raw_role = claims.get("role")
    try:
        role = Role(raw_role) if raw_role is not None else Role.DATER
    except ValueError:
        role = Role.DATER
    return StubUser(id=user_id, role=role)


class StubAuthMiddleware(AbstractAuthenticationMiddleware):
    """Trust-the-token bearer auth — decodes `sub`, never verifies the signature."""

    async def authenticate_request(self, connection: ASGIConnection) -> AuthenticationResult:
        auth_header = connection.headers.get("Authorization", "")
        scheme, _, token = auth_header.partition(" ")

        user: StubUser | None = None
        if scheme.lower() == "bearer" and token:
            claims = _decode_jwt_unverified(token)
            if claims is not None:
                user = _user_from_claims(claims)

        # `auth` carries the raw token for handlers that need it (none yet).
        return AuthenticationResult(user=user, auth=token or None)
