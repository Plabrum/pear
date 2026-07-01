from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, synonym

from app.domain.contacts.enums import WingpersonStatus
from app.platform.base.models import BaseDBModel
from app.utils.textenum import TextEnum


class Contact(BaseDBModel):
    __tablename__ = "contacts"

    # the dater who owns this contact — SQL: not null references profiles(id) on delete cascade
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    phone_number: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # set once the invitee signs up & accepts — SQL: references profiles(id) on delete set null
    winger_id: Mapped[UUID | None] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    wingperson_status: Mapped[WingpersonStatus] = mapped_column(
        TextEnum(WingpersonStatus),
        nullable=False,
        default=WingpersonStatus.INVITED,
        server_default=WingpersonStatus.INVITED.name,
    )

    # `wingperson_status` IS this contact's state-machine column, but the platform
    # `StateMachineService` reads/writes a uniformly-named `obj.state`. Expose a
    # `state` synonym so contacts go through the same transition machinery as any
    # `StateMachineMixin` model WITHOUT renaming the wire/SQL column. Additive only:
    # the underlying TEXT column is still `wingperson_status`; `get_state_machine_meta`
    # (which inspects `__table__.columns["state"]`) returns None here — intended, the
    # contacts machine is invoked explicitly by its actions, not via column discovery.
    state: Mapped[WingpersonStatus] = synonym("wingperson_status")
