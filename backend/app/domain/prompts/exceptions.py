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
