# The reports domain is write-only: its single endpoint, `POST /reports`, is the
# `FileReport` action in `actions.py`, exposed through the generic actions router.
# `reports_router` is exported with no route handlers so it mounts uniformly with
# every other domain, and remains the mount point should a read (e.g. an admin
# report list) ever be added. `guards=[requires_session]` keeps the surface
# authenticated even while empty.

from __future__ import annotations

from litestar import Router

from app.platform.auth.guards import requires_session

reports_router = Router(
    path="",
    route_handlers=[],
    tags=["reports"],
    guards=[requires_session],
)
