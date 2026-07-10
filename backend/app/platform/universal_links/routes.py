# Serves the two static-ish endpoints Associated Domains universal links need,
# both hosted straight from the backend (not a separate infra static-file
# pipeline — see the Caddyfile's `{$DOMAIN}` block, which just reverse-proxies
# the apex to this same API container). Both are unauthenticated, unversioned,
# and content-only — no DB access.
#
# A Vercel-hosted marketing landing page is planned to take over the apex
# domain soon (see infra/modules/ec2_stack/main.tf's `aws_route53_record.apex`
# comment). These two routes must keep resolving at the apex after that move —
# via a `rewrites()` proxy in the landing project, not by porting this logic
# into the landing repo — so nothing here needs to change when that happens.
from __future__ import annotations

import json

from litestar import Response, get

from app.config import config

_APP_STORE_URL = "https://apps.apple.com/app/pear/id6744145981"
_BUNDLE_ID = "com.plabrum.pear"


@get("/.well-known/apple-app-site-association", exclude_from_auth=True)
async def apple_app_site_association() -> Response:
    """iOS fetches this (over HTTPS, no redirects) to verify Associated Domains.

    Must be valid JSON served with `Content-Type: application/json` — no
    extension, no redirect. `appID` is `<team_id>.<bundle_id>`; `paths` scopes
    which URL paths iOS is allowed to hand to the app instead of Safari.
    """
    body = {
        "applinks": {
            "details": [
                {
                    "appID": f"{config.APPLE_TEAM_ID}.{_BUNDLE_ID}",
                    "paths": ["/invite", "/invite/*"],
                }
            ]
        }
    }
    return Response(content=json.dumps(body), media_type="application/json")


@get("/invite", exclude_from_auth=True)
async def invite_landing() -> Response:
    """Fallback landing page for `/invite*` links opened without the app installed.

    Reached only when Associated Domains doesn't hand the link to the app (app
    not installed, or opened outside Safari/Messages) — with the app installed,
    iOS opens it directly and this route is never hit.
    """
    html = f"""<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Pear</title>
    <style>
      body {{
        font-family: -apple-system, BlinkMacSystemFont, sans-serif;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        min-height: 100vh;
        margin: 0;
        padding: 24px;
        text-align: center;
        background: #F5F1E8;
        color: #1a1a1a;
      }}
      h1 {{ font-size: 22px; margin-bottom: 8px; }}
      p {{ color: #555; margin-bottom: 24px; }}
      a {{
        display: inline-block;
        padding: 12px 24px;
        border-radius: 24px;
        background: #2f6b4f;
        color: white;
        text-decoration: none;
        font-weight: 600;
        margin: 6px;
      }}
      a.secondary {{ background: transparent; color: #2f6b4f; border: 1px solid #2f6b4f; }}
    </style>
  </head>
  <body>
    <h1>Open this invite in Pear</h1>
    <p>Get the app to accept your wingperson invite.</p>
    <a href="{_APP_STORE_URL}">Get it on the App Store</a>
    <a class="secondary" href="pear://invite">Open in Pear</a>
  </body>
</html>"""
    return Response(content=html, media_type="text/html")


universal_links_router = [apple_app_site_association, invite_landing]
