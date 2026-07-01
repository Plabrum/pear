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

    Any object exposing a UUID `id` and a `Role` satisfies the transition contract.
    """

    @property
    def id(self) -> UUID: ...

    @property
    def role(self) -> Role: ...
