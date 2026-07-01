"""Users-domain model surface.

`app.platform.actions.deps.ActionDeps` forward-references `User` from this exact
module path (`app.domain.users.models.User`). Litestar resolves that dataclass's
type hints at request time, so the name must exist at RUNTIME — not just under
`TYPE_CHECKING`.

Phase 4: `User` is the real authenticated request principal
(`app.platform.auth.principal.User`) — loaded from the `profiles` table after the
access token's ES256 signature is verified. It satisfies the structural `Actor`
protocol (`.id: UUID`, `.role: Role`) the actions/state-machine layers expect.

This module deliberately exposes NO SQLAlchemy model (no `__tablename__`) so model
discovery does not register a `users` table — the identity anchor is `profiles`
(Phase 3), and auth state lives in `auth_identities` / `refresh_tokens`.
"""

from app.platform.auth.principal import User

# Runtime-resolvable name for `ActionDeps.user`'s forward reference.
__all__ = ["User"]
