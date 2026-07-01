"""STUB users-domain model surface (Phase 2).

`app.platform.actions.deps.ActionDeps` forward-references `User` from this exact
module path (`app.domain.users.models.User`). Litestar resolves that dataclass's
type hints at request time, so the name must exist at RUNTIME — not just under
`TYPE_CHECKING`. Until the real users domain lands (Phase 3/4), `User` is an alias
of the STUB request principal (`app.platform.auth.models.StubUser`), which already
satisfies the structural `Actor` protocol the actions/state-machine layers expect.

This module deliberately exposes NO SQLAlchemy model (no `__tablename__`) so model
discovery does not register a `users` table prematurely — the real table is Phase 3.

TODO(Phase 3/4): replace `StubUser` with the real DB-backed `User` model.
"""

from app.platform.auth.models import StubUser

# Runtime-resolvable name for `ActionDeps.user`'s forward reference.
User = StubUser

__all__ = ["User"]
