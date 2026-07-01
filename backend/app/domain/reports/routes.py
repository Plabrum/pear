# The reports domain owns only its model + queries now: the write lives on the
# DatingProfile `Report` action (target in the URL), so `reports/` has no action of
# its own. `reports_router` is exported with no route handlers so the mount stays
# uniform with every other domain, and remains the mount point should a read (e.g.
# an admin report list) ever be added. `guards=[requires_session]` keeps the
# surface authenticated even while empty.

from __future__ import annotations

from litestar import Router

from app.platform.auth.guards import requires_session

reports_router = Router(
    path="",
    route_handlers=[],
    tags=["reports"],
    guards=[requires_session],
)
