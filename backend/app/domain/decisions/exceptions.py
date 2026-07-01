"""Typed, user-facing errors for the decisions domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. The class name is the contract — no ad-hoc response strings in handlers.
These reproduce the explicit `HTTPException` status codes from the Hono route:

  * 400 — deciding on yourself / suggesting the dater to themselves.
  * 404 — no pending suggestion to act on.
  * 403 — caller is not an active wingperson for this dater (also enforced by RLS).
"""

from app.utils.exceptions import ApplicationError


class CannotDecideOnSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot decide on yourself"


class CannotSuggestSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot suggest the dater to themselves"


class NoPendingSuggestionError(ApplicationError):
    status_code = 404
    detail = "No pending suggestion to act on"


class NotActiveWingpersonError(ApplicationError):
    status_code = 403
    detail = "No active wingperson relationship"
