from app.utils.exceptions import ApplicationError


class DatingProfileNotFoundError(ApplicationError):
    status_code = 404
    detail = "Dating profile not found"


class NotDaterOrWingpersonError(ApplicationError):
    status_code = 403
    detail = "Not the dater or an active wingperson"
