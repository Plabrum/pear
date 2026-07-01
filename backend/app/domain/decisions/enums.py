"""Decisions-domain enums.

Stored as TEXT via `TextEnum` (see app.utils.textenum). Member *values* match the
Postgres `public.decision_type` enum labels exactly:

    decision_type -> 'approved' | 'declined'

Note: in the SQL the `decisions.decision` column is *nullable* — a NULL decision is
a wingperson suggestion that has not yet been acted on. The nullability lives on the
column (Mapped[DecisionType | None]), not in this enum.
"""

from enum import Enum


class DecisionType(Enum):
    APPROVED = "approved"
    DECLINED = "declined"
