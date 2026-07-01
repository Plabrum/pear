"""Read endpoints for the reports domain (READS ONLY).

The Hono `reports` domain (`supabase/functions/api/domains/reports/route.ts`) is
WRITE-ONLY — its single endpoint is `POST /reports`, which is ported to the
`FileReport` action in `actions.py` and exposed through the generic actions router
(`POST /actions/{group}/{object_id}`). There are therefore NO read endpoints here.

`reports_router` is still exported (with no route handlers) so the Integrate stage
can append it to `factory.py`'s `route_handlers` uniformly with every other domain,
and so this module remains the documented mount point should a read (e.g. an admin
report list) ever be added. `guards=[requires_session]` keeps the surface
authenticated even while empty.
"""

from __future__ import annotations

from litestar import Router

from app.platform.auth.guards import requires_session

reports_router = Router(
    path="",
    route_handlers=[],
    tags=["reports"],
    guards=[requires_session],
)
