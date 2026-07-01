import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.contacts.enums import WingpersonStatus
from app.platform.base.rls import Owner, RLSScopedMixin
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
