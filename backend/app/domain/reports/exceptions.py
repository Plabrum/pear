from app.utils.exceptions import ApplicationError


class CannotReportSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot report yourself"
