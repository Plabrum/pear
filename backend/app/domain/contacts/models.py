from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.contacts.enums import WingpersonStatus
from app.platform.base.models import BaseDBModel
from app.platform.base.rls import Anyone, Owner, RLSScopedMixin
from app.platform.state_machine.models import StateMachineMixin
from app.utils.sqids import Sqid, SqidType


class Contact(
    StateMachineMixin(state_enum=WingpersonStatus, initial_state=WingpersonStatus.INVITED),
    # Both parties (dater + winger) read and update; only the dater creates/removes.
    RLSScopedMixin(
        read=Owner("user_id") | Owner("winger_id"),
        edit={
            "INSERT": Owner("user_id"),
            "UPDATE": Owner("user_id") | Owner("winger_id"),
            "DELETE": Owner("user_id"),
        },
    ),
):
    __tablename__ = "contacts"

    # the dater who owns this contact — SQL: not null references profiles(id) on delete cascade
    user_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # set once the invitee signs up & accepts — SQL: references profiles(id) on delete set null
    winger_id: Mapped[Sqid | None] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # `state` (the wing relationship lifecycle: invited|active|removed) is the
    # canonical TextEnum column added by StateMachineMixin — driven exclusively
    # through StateMachineService.transition by the contact actions.


# Bearer-secret table: mint + consume both run UNAUTHENTICATED (no app.user_id), and
# the consume looks the row up by an unguessable token_hash. The real floor is the
# HMAC-hashed secret, not the actor — mirrors `MagicLinkToken`. No DELETE granted.
class WingpersonInviteToken(BaseDBModel, RLSScopedMixin(read=Anyone, edit={"INSERT": Anyone, "UPDATE": Anyone})):
    """Single-use, TTL-bound bearer token for a wingperson-invite link.

    Mint+consume run unauthenticated, so RLS is `Anyone` — the HMAC hash is the
    security floor, not row ownership.
    """

    __tablename__ = "wingperson_invite_tokens"

    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, nullable=False)
    contact_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("contacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(sa.DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), default=None)
