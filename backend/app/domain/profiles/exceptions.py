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
