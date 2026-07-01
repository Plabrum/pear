from app.utils.exceptions import ApplicationError


class MediaNotFoundError(ApplicationError):
    status_code = 404
    detail = "Media not found"
