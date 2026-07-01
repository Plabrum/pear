from litestar import Request, Response


class ApplicationError(Exception):
    """Base class for all application-level errors.

    Subclass this and set `status_code` + `detail` to create typed HTTP errors
    that are handled automatically by the exception handler registered in factory.py.

    Example:
        class NotFoundError(ApplicationError):
            status_code = 404
            detail = "Resource not found"
    """

    status_code: int = 500
    detail: str = "An unexpected error occurred"

    def __init__(self, detail: str | None = None, status_code: int | None = None) -> None:
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


def exception_to_http_response(request: Request, exc: ApplicationError) -> Response:
    """Convert an ApplicationError into a JSON HTTP response."""
    return Response(
        content={"detail": exc.detail},
        status_code=exc.status_code,
    )
