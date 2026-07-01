from enum import StrEnum, auto


class TaskName(StrEnum):
    HEALTH_CHECK = auto()
    SEND_EMAIL = auto()
    # Reap a dead push token (APNs 410 Unregistered) — runs in SYSTEM mode.
    REAP_PUSH_TOKEN = auto()
    # Fan-out / broadcast push to many recipients — keeps the request unblocked.
    SEND_PUSH = auto()
    # Normalize an uploaded image to WebP (worker-driven) — runs in SYSTEM mode.
    PROCESS_IMAGE = auto()
    # Idempotently form a match for a mutually-approved pair — runs in SYSTEM mode.
    FORM_MATCH = auto()


class TaskRoleType(StrEnum):
    """RLS context a task transaction runs under.

    USER  — sets `app.user_id` so RLS policies scope to a single user.
    SYSTEM — system-actor transitions (e.g. queue-driven side effects) that run
             without a user scope. Pear has no organization concept; system tasks
             simply omit the per-user GUC.
    """

    USER = auto()
    SYSTEM = auto()


class TaskStatus(StrEnum):
    PENDING = auto()
    ACTIVE = auto()
    COMPLETE = auto()
    FAILED = auto()
    ABORTED = auto()
