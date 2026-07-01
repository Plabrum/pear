from enum import Enum


class DecisionState(Enum):
    # A winger-suggested card the dater has not yet acted on (the former NULL decision).
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


# Backwards-compat alias: the pre-state-machine initial-schema migration imports
# `DecisionType` for the now-removed nullable `decision` column's `TextEnum`. The
# TextEnum compiles to TEXT regardless of the enum class, so the historical DDL is
# unchanged; this only keeps that immutable revision importable.
DecisionType = DecisionState
