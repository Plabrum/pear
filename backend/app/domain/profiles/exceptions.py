"""Typed, user-facing errors for the profiles domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. The class name is the contract — no ad-hoc response strings in handlers.
These reproduce the explicit `HTTPException` status codes from the Hono route:
404 (profile / dating profile not found) and 409 (dating profile already exists).
"""

from app.utils.exceptions import ApplicationError


class ProfileNotFoundError(ApplicationError):
    status_code = 404
    detail = "Profile not found"


class DatingProfileNotFoundError(ApplicationError):
    status_code = 404
    detail = "Dating profile not found"


class DatingProfileAlreadyExistsError(ApplicationError):
    status_code = 409
    detail = "Dating profile already exists"
