"""Typed, user-facing errors for the contacts domain.

Subclass `ApplicationError` so the handler registered in `factory.py`
(`exception_to_http_response`) renders them as `{"detail": …}` with the right
status. The class name is the contract — no ad-hoc response strings in handlers.

The Hono route returned 404 when accept/decline/remove matched no row for the
caller (`No pending invitation` / `Contact not found`). In the Litestar port the
action framework already raises `PermissionDeniedException` (403) when an action's
`is_available` gate is False, and `NotFoundException` (404) when the object_id
resolves to no visible row — so these are kept for the few places an action needs
to signal a domain-specific failure beyond gating (currently none beyond the
framework defaults; retained for parity + future use).
"""

from app.utils.exceptions import ApplicationError


class ContactNotFoundError(ApplicationError):
    status_code = 404
    detail = "Contact not found"


class NoPendingInvitationError(ApplicationError):
    status_code = 404
    detail = "No pending invitation"
