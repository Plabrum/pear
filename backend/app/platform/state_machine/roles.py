"""Caller roles for state-machine transitions.

Adapted from sloopquest's `app.domain.users.roles.Role`. Pear has two real
roles — a dater and their trusted winger — plus a SYSTEM sentinel used by
`StateMachineService.system_transition` for machine-driven edges (e.g. a match
auto-created when both sides approve). Pear has no domain `User` model yet
(later phase), so this lives in the platform layer rather than under a users
domain.
"""

from __future__ import annotations

from enum import StrEnum, auto
from typing import Protocol
from uuid import UUID


class Role(StrEnum):
    DATER = auto()
    WINGER = auto()
    SYSTEM = auto()


class Actor(Protocol):
    """Structural type for the caller of a human-initiated transition.

    Pear's concrete `User` model lands in a later phase; until then any object
    exposing a UUID `id` and a `Role` satisfies the transition contract.
    """

    @property
    def id(self) -> UUID: ...

    @property
    def role(self) -> Role: ...
