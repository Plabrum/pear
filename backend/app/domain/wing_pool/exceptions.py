from app.utils.exceptions import ApplicationError


class NotActiveWingpersonError(ApplicationError):
    status_code = 403
    detail = "No active wingperson relationship"
