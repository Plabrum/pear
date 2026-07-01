"""Photos-domain enums.

The original Supabase schema models a photo's approval as two nullable timestamp
columns rather than a status enum:

    approved_at  -> non-null once approved (pending otherwise)
    rejected_at  -> non-null once a winger-suggested photo is rejected by the dater

To gate the approve/reject mutations through the platform `StateMachineService`
(see `state_machine.py`) we surface that timestamp pair as a derived three-state
lifecycle. `PhotoApprovalState` is NOT persisted as its own column — the machine's
`on_enter` hooks write the underlying `approved_at` / `rejected_at` columns, and a
read-only `state` property on `ProfilePhoto` (attached in `state_machine.py`)
derives the current value. Member *values* are lowercase for a stable, readable
audit-log / event representation.
"""

from enum import Enum


class PhotoApprovalState(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
