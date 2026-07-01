from app.utils.exceptions import ApplicationError


class MatchNotFoundError(ApplicationError):
    status_code = 404
    detail = "Match not found"
