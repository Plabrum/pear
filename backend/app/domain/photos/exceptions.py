"""Typed, user-facing errors for the photos domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. These reproduce the explicit `HTTPException` status codes from the Hono
route: 404 (dating profile / photo not found) and 403 (caller is neither the dater
nor an active wingperson).

Gate denials surfaced via an action's `is_available` returning False are raised by
the action framework as a `PermissionDeniedException` (403) automatically — these
classes cover the create / upload paths where the caller passes an explicit
`datingProfileId` and the authorization check is data-dependent rather than a pure
state gate.
"""

from app.utils.exceptions import ApplicationError


class DatingProfileNotFoundError(ApplicationError):
    status_code = 404
    detail = "Dating profile not found"


class NotDaterOrWingpersonError(ApplicationError):
    status_code = 403
    detail = "Not the dater or an active wingperson"


class PhotoNotFoundError(ApplicationError):
    status_code = 404
    detail = "Photo not found"
