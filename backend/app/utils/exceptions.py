from litestar import Request, Response


class ApplicationError(Exception):
    """Base class for all application-level errors.

    Subclass this and set `status_code` + `detail` to create typed HTTP errors
    that are handled automatically by the exception handler registered in factory.py.

    `user_facing` controls whether `detail` is safe to show an end user. It is
    False by default: most `detail` strings are developer-oriented (internal
    state, lookup keys, stack context) and must NOT reach a toast. The client
    surfaces `detail` only when `user_facing` is True; otherwise it shows generic
    copy. Raise `UserFacingError` (below) for the opt-in case.

    Example:
        class NotFoundError(ApplicationError):
            status_code = 404
            detail = "Resource not found"
    """

    status_code: int = 500
    detail: str = "An unexpected error occurred"
    user_facing: bool = False

    def __init__(self, detail: str | None = None, status_code: int | None = None) -> None:
        if detail is not None:
            self.detail = detail
        if status_code is not None:
            self.status_code = status_code
        super().__init__(self.detail)


class UserFacingError(ApplicationError):
    """An expected, actionable failure whose `detail` is written FOR the end user.

    Raise this — not a bare `ApplicationError` / Litestar exception — when the
    message itself is the point: a duplicate invite, an expired link, a
    rate-limited action. `detail` must read as a complete, friendly sentence; the
    client displays it verbatim. Defaults to 409 (Conflict); pass `status_code`
    for a different code.
    """

    status_code: int = 409
    detail: str = "Something went wrong."
    user_facing: bool = True


def exception_to_http_response(request: Request, exc: ApplicationError) -> Response:
    """Convert an ApplicationError into a JSON HTTP response.

    `user_facing` rides along so the client knows whether `detail` is safe to
    surface to the user (see `UserFacingError`).
    """
    return Response(
        content={"detail": exc.detail, "user_facing": exc.user_facing},
        status_code=exc.status_code,
    )
