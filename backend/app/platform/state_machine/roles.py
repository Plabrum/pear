from __future__ import annotations

from enum import StrEnum, auto
from typing import Protocol

from app.utils.sqids import Sqid


class Role(StrEnum):
    DATER = auto()
    WINGER = auto()
    SYSTEM = auto()


class Actor(Protocol):
    """Structural type for the caller of a human-initiated transition.

    Any object exposing a Sqid/int `id` and a `Role` satisfies the transition contract.
    """

    @property
    def id(self) -> Sqid: ...

    @property
    def role(self) -> Role: ...
