from __future__ import annotations

from enum import StrEnum
from typing import ClassVar

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import config
from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.contacts.queries import (
    fetch_push_token,
    find_profile_id_by_phone,
    has_live_contact,
)
from app.domain.contacts.schemas import AcceptInviteByTokenData, InviteWingpersonData
from app.domain.contacts.service import ContactService
from app.domain.contacts.state_machine import contact_machine
from app.platform.actions.base import (
    BaseObjectAction,
    BaseTopLevelAction,
    EmptyActionData,
    action_group_factory,
)
from app.platform.actions.deps import ActionDeps
from app.platform.actions.enums import ActionGroupType, ActionIcon
from app.platform.actions.schemas import ActionExecutionResponse
from app.platform.auth.principal import User
from app.platform.state_machine.roles import Role
from app.utils.exceptions import UserFacingError


class ContactActionKey(StrEnum):
    INVITE = "invite"
    ACCEPT = "accept"
    ACCEPT_BY_TOKEN = "accept_by_token"
    DECLINE = "decline"
    REMOVE = "remove"


contact_actions = action_group_factory(
    ActionGroupType.CONTACT_ACTIONS,
    default_invalidation="/wingpeople",
    model_type=Contact,
)


# ── POST /wingpeople/invite ────────────────────────────────────────────────────


@contact_actions
class InviteWingperson(BaseTopLevelAction[InviteWingpersonData]):
    action_key: ClassVar[ContactActionKey] = ContactActionKey.INVITE
    label = "Invite Wingperson"
    icon = ActionIcon.ADD

    @classmethod
    async def execute(
        cls,
        data: InviteWingpersonData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        # Reject a duplicate invite up front with a message the client shows
        # verbatim (UserFacingError → user_facing=True). A `removed` contact does
        # not block re-inviting.
        if await has_live_contact(transaction, user.id, data.phoneNumber):
            raise UserFacingError("You've already invited this person.")

        # If a profile already exists with that phone number, link winger_id
        # immediately — the case where the invitee is already a Pear user.
        #
        # TODO: the other half of auto-linking — linking pre-existing pending
        # contacts when a NEW phone registers — should also fire at
        # profile/phone-set time (a hook in the auth/profiles flow), not only here
        # at invite time. Kept in the invite action for now.
        winger_id = await find_profile_id_by_phone(transaction, data.phoneNumber)

        contact = Contact(
            user_id=user.id,
            phone_number=data.phoneNumber,
            winger_id=winger_id,
            state=WingpersonStatus.INVITED,
        )
        transaction.add(contact)
        await transaction.flush()

        if winger_id is not None:
            winger_token = await fetch_push_token(transaction, winger_id)
            if winger_token is not None:
                await deps.push.send(
                    winger_token,
                    "You've been invited! 🤝",
                    "Someone wants you to be their wingperson on Pear.",
                )

        contact_service = ContactService(db=transaction, config=deps.config)
        token = await contact_service.issue_invite_token(contact.id)
        # Must be the apex (UNIVERSAL_LINK_BASE_URL), not API_BASE_URL's api.<domain>
        # subdomain — the Associated Domains entitlement only covers usepear.app.
        invite_url = f"{config.UNIVERSAL_LINK_BASE_URL}/invite/verify?token={token}"

        return ActionExecutionResponse(
            message="Invitation sent",
            invalidate_queries=["/wingpeople", "/winger-tabs"],
            created_id=contact.id,
            invite_url=invite_url,
        )


# ── POST /wingpeople/{id}/accept ───────────────────────────────────────────────


@contact_actions
class AcceptInvite(BaseObjectAction[Contact, EmptyActionData]):
    action_key: ClassVar[ContactActionKey] = ContactActionKey.ACCEPT
    label = "Accept"
    icon = ActionIcon.CHECK
    target_state = WingpersonStatus.ACTIVE

    @classmethod
    def is_available(cls, obj: Contact, user: User, deps: ActionDeps) -> bool:
        # Only the linked winger may accept, and only while still invited.
        return obj.winger_id == user.id and user.role is Role.WINGER and obj.state == WingpersonStatus.INVITED

    @classmethod
    async def execute(
        cls,
        obj: Contact,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await deps.state_machine_service.transition(
            contact_machine,
            obj,
            WingpersonStatus.ACTIVE,
            actor=user,
        )
        return ActionExecutionResponse(
            message="Invitation accepted",
            invalidate_queries=["/wingpeople", "/winger-tabs"],
        )


# ── POST /actions/contact_actions (top-level) — accept via invite link ─────────


@contact_actions
class AcceptInviteByToken(BaseTopLevelAction[AcceptInviteByTokenData]):
    """Accept a wingperson invite from the token in a shared link.

    `AcceptInvite` (above) only works once `winger_id` is already resolved to the
    caller (phone-match at invite time, or by an already-registered invitee tapping
    Accept from their in-app invitations list) — a brand-new invitee's `Contact` row
    can't even be RLS-read by them yet (`Owner("user_id") | Owner("winger_id")`), so
    the existing object-action dispatch is unusable. This top-level action instead
    resolves the token itself, links `winger_id` on first use, and converges on the
    same `ACTIVE` state.
    """

    action_key: ClassVar[ContactActionKey] = ContactActionKey.ACCEPT_BY_TOKEN
    label = "Accept Invite"
    icon = ActionIcon.CHECK
    target_state = WingpersonStatus.ACTIVE
    # Not a generically-available action — the invite screen calls it directly with
    # a token from a deep link. Hidden from `GET /actions/contact_actions`'s list.
    is_hidden = True

    @classmethod
    async def execute(
        cls,
        data: AcceptInviteByTokenData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        contact_service = ContactService(db=transaction, config=deps.config)
        contact = await contact_service.preview_invite_token(data.token)
        if contact is None:
            raise UserFacingError("This invite link is invalid or has expired.")
        if contact.state != WingpersonStatus.INVITED:
            raise UserFacingError("This invite is no longer available.")
        if contact.winger_id is not None and contact.winger_id != user.id:
            raise UserFacingError("This invite has already been claimed by someone else.")

        if contact.winger_id is None:
            contact.winger_id = user.id
            await transaction.flush()

        await deps.state_machine_service.transition(
            contact_machine,
            contact,
            WingpersonStatus.ACTIVE,
            actor=user,
        )
        await contact_service.finalize_invite_token(data.token)

        return ActionExecutionResponse(
            message="Invitation accepted",
            invalidate_queries=["/wingpeople", "/winger-tabs"],
        )


# ── POST /wingpeople/{id}/decline ──────────────────────────────────────────────


@contact_actions
class DeclineInvite(BaseObjectAction[Contact, EmptyActionData]):
    action_key: ClassVar[ContactActionKey] = ContactActionKey.DECLINE
    label = "Decline"
    icon = ActionIcon.X
    target_state = WingpersonStatus.REMOVED

    @classmethod
    def is_available(cls, obj: Contact, user: User, deps: ActionDeps) -> bool:
        # Only the linked winger may decline, and only while still invited.
        return obj.winger_id == user.id and user.role is Role.WINGER and obj.state == WingpersonStatus.INVITED

    @classmethod
    async def execute(
        cls,
        obj: Contact,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await deps.state_machine_service.transition(
            contact_machine,
            obj,
            WingpersonStatus.REMOVED,
            actor=user,
        )
        return ActionExecutionResponse(
            message="Invitation declined",
            invalidate_queries=["/wingpeople", "/winger-tabs"],
        )


# ── DELETE /wingpeople/{id} ────────────────────────────────────────────────────


@contact_actions
class RemoveWingperson(BaseObjectAction[Contact, EmptyActionData]):
    action_key: ClassVar[ContactActionKey] = ContactActionKey.REMOVE
    label = "Remove"
    icon = ActionIcon.TRASH
    confirmation_message = "Remove this wingperson?"
    target_state = WingpersonStatus.REMOVED

    @classmethod
    def is_available(cls, obj: Contact, user: User, deps: ActionDeps) -> bool:
        # The dater who owns the contact may remove it while it is invited (cancel)
        # or active (remove) — but not once it is already removed (terminal).
        return (
            obj.user_id == user.id
            and user.role is Role.DATER
            and obj.state in (WingpersonStatus.INVITED, WingpersonStatus.ACTIVE)
        )

    @classmethod
    async def execute(
        cls,
        obj: Contact,
        data: EmptyActionData,
        transaction: AsyncSession,
        user: User,
        deps: ActionDeps,
    ) -> ActionExecutionResponse:
        await deps.state_machine_service.transition(
            contact_machine,
            obj,
            WingpersonStatus.REMOVED,
            actor=user,
        )
        return ActionExecutionResponse(
            message="Wingperson removed",
            invalidate_queries=["/wingpeople", "/winger-tabs"],
        )
