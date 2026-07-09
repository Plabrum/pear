from enum import Enum


class DecisionState(Enum):
    # A winger-suggested card the dater has not yet acted on.
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"


# Kept only because an immutable Alembic revision imports `DecisionType` — do not remove.
DecisionType = DecisionState
