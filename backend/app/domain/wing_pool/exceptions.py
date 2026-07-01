"""Typed, user-facing errors for the wing-pool domain.

Reproduces the Hono route's `HTTPException(403, ...)` when the caller is not an
active wingperson for the requested dater. Subclasses `ApplicationError` so the
handler registered in `factory.py` renders it as `{"detail": …}` with status 403.
"""

from app.utils.exceptions import ApplicationError


class NotActiveWingpersonError(ApplicationError):
    status_code = 403
    detail = "No active wingperson relationship"
