"""Typed, user-facing errors for the prompts domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. The class name is the contract — no ad-hoc response strings in handlers.
These reproduce the explicit `HTTPException` status codes from the Hono route:
404 (prompt / dating profile not found) and 403 (caller is neither a wingperson
nor a match of the prompt owner).
"""

from app.utils.exceptions import ApplicationError


class DatingProfileNotFoundError(ApplicationError):
    status_code = 404
    detail = "No dating profile"


class ProfilePromptNotFoundError(ApplicationError):
    status_code = 404
    detail = "Profile prompt not found"


class NotWingpersonOrMatchError(ApplicationError):
    status_code = 403
    detail = "Not a wingperson or match of the prompt owner"
