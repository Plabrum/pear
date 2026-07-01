from app.utils.exceptions import ApplicationError


class CannotDecideOnSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot decide on yourself"


class CannotSuggestSelfError(ApplicationError):
    status_code = 400
    detail = "Cannot suggest the dater to themselves"


class NoPendingSuggestionError(ApplicationError):
    status_code = 404
    detail = "No pending suggestion to act on"


class NotActiveWingpersonError(ApplicationError):
    status_code = 403
    detail = "No active wingperson relationship"
