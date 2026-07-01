"""Typed, user-facing errors for the messages domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. Reproduces the Hono route's `HTTPException(404, 'Match not found')` for
the "match not found OR viewer is not party to it" case — the server never
distinguishes the two, to avoid match-id enumeration.
"""

from app.utils.exceptions import ApplicationError


class MatchNotFoundError(ApplicationError):
    status_code = 404
    detail = "Match not found"
