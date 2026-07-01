from app.utils.exceptions import ApplicationError


class ContactNotFoundError(ApplicationError):
    status_code = 404
    detail = "Contact not found"


class NoPendingInvitationError(ApplicationError):
    status_code = 404
    detail = "No pending invitation"
