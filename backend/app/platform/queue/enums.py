from enum import StrEnum, auto


class TaskName(StrEnum):
    HEALTH_CHECK = auto()
    SEND_EMAIL = auto()
    # Reap a dead push token (APNs 410 Unregistered) — runs in SYSTEM mode.
    REAP_PUSH_TOKEN = auto()
    # Fan-out / broadcast push to many recipients — keeps the request unblocked.
    SEND_PUSH = auto()


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
