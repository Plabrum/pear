"""Typed, user-facing errors for the reports domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. The class name is the contract — no ad-hoc response strings in handlers.
Reproduces the explicit `HTTPException` status code from the Hono route:

  * 400 — reporting yourself (`reporterId === recipientId`).
"""

from app.utils.exceptions import ApplicationError


class CannotReportSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot report yourself"
