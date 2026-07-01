"""State machine exceptions."""

from app.utils.exceptions import ApplicationError


class InvalidTransitionError(ApplicationError):
    """Raised when a state transition is not allowed.

    Covers both topology violations (edge doesn't exist) and
    role violations (caller lacks required role).
    """

    status_code = 409

    def __init__(self, detail: str = "Invalid state transition") -> None:
        super().__init__(detail)
        self.detail = detail
