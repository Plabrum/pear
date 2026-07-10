from __future__ import annotations

from litestar import Router, get, post
from litestar.exceptions import NotAuthorizedException
from litestar.response import Redirect

from app.config import config
from app.domain.contacts.schemas import InviteVerifyIn, InviteVerifyOut
from app.domain.contacts.service import ContactService
from app.domain.profiles.models import Profile


@get("/invite/verify", exclude_from_auth=True)
async def invite_verify_redirect(token: str) -> Redirect:
    """Universal-link/SMS hop: 302 the browser into the app's deep-link scheme.

    Does NOT consume the token — the app extracts it and POSTs it back to the
    `verify` endpoint below, mirroring the magic-link flow.
    """
    target = f"{config.APP_DEEP_LINK_SCHEME}://invite?token={token}"
    return Redirect(path=target, status_code=302)


@post("/invite/verify", exclude_from_auth=True)
async def invite_verify(data: InviteVerifyIn, contact_service: ContactService) -> InviteVerifyOut:
    """Preview an invite token's target contact — read-only, repeatable.

    Does not consume the token (see `ContactService.preview_invite_token`'s
    docstring for why preview and finalize are split for this flow).
    """
    contact = await contact_service.preview_invite_token(data.token)
    if contact is None:
        raise NotAuthorizedException("Invalid or expired invite")

    dater = await contact_service.db.get(Profile, contact.user_id)
    return InviteVerifyOut(
        contactId=contact.id,
        daterName=dater.chosen_name if dater is not None else None,
        alreadyLinked=contact.winger_id is not None,
    )


invite_router = Router(
    path="",
    route_handlers=[invite_verify_redirect, invite_verify],
    tags=["contacts"],
)
