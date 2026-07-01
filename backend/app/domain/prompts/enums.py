"""Prompts-domain enums.

The `prompt_responses` approval lifecycle is modeled here as a `ApprovalState`
enum even though the underlying table (Phase 3 `models.py`) stores it as two
booleans (`is_approved` / `is_rejected`) rather than a single status column. The
enum is the *state-machine* representation: the machine in `state_machine.py`
transitions over these three states, and a thin adapter (see `state_machine.py`)
projects the booleans onto `ApprovalState` and back so the platform
`StateMachineService` — which operates on a single `state` attribute — can drive
the boolean columns without the model needing a dedicated status column.

  * PENDING  -> is_approved=False, is_rejected=False  (initial)
  * APPROVED -> is_approved=True,  is_rejected=False
  * REJECTED -> is_approved=False, is_rejected=True
"""

from enum import Enum


class ApprovalState(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
