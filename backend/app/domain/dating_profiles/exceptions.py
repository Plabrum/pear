from app.utils.exceptions import ApplicationError


class NotActiveWingpersonError(ApplicationError):
    status_code = 403
    detail = "No active wingperson relationship"


class CannotSuggestSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot suggest the dater to themselves"
