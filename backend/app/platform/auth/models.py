"""Minimal in-memory user identity for the STUB auth layer.

Pear's concrete `User` DB model lands in a later phase (Phase 3/4 — profiles +
auth provider). Until then the request principal is a tiny dataclass built from
the decoded (unverified) JWT `sub`. It satisfies the structural `Actor` protocol
(`.id: UUID`, `.role: Role`) consumed by the state machine and the actions layer,
so platform code can be exercised end-to-end without a users domain.
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.platform.state_machine.roles import Role


@dataclass
class StubUser:
    """Request principal derived from a decoded JWT `sub` claim.

    TODO(Phase 4): replace with the real `app.domain.users.models.User` loaded
    from the database once the auth provider + profiles table exist.
    """

    id: UUID
    role: Role = Role.DATER
