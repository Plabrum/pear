"""Contact model — the dater ↔ winger address-book relationship.

Ports `public.contacts` from 20260228000000_schema.sql:

    user_id      = the dater (who wants a wingperson)
    phone_number = phone used to send the invite SMS
    winger_id    = set once the invitee creates an account and accepts (nullable)
    wingperson_status = invited | active | removed

Deviations from the SQL (per the migration plan):
  * `id` UUID PK + `created_at` are inherited from BaseDBModel (the SQL's ad-hoc
    `created_at` is subsumed; `updated_at`/`deleted_at` are additive and harmless).
  * `wingperson_status` is TEXT via `TextEnum`, not a Postgres native enum.
  * FK ondelete semantics mirror the SQL: user_id CASCADE, winger_id SET NULL.
  * The auto_link_pending_contacts trigger is NOT ported (Phase 4/5).
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

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
