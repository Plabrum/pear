class CommittableTaskError(Exception):
    """Base class for task exceptions that should commit the transaction before re-raising.

    Raise a subclass when a task fails in a way that has already written meaningful
    state to the session (e.g. a FAILED status row) that must be persisted so that
    retries or monitoring can see it.

    Any exception that does NOT inherit from this class will roll back the transaction.
    """
