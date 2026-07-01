import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.decisions.enums import DecisionState
from app.platform.base.rls import Owner, OwnerOrWinger, RLSScopedMixin
from app.platform.state_machine.models import StateMachineMixin
from app.utils.sqids import Sqid, SqidType


class Decision(
    StateMachineMixin(state_enum=DecisionState, initial_state=DecisionState.PENDING),
    # Visible to actor / recipient / suggester. Insert as the actor or as an active
    # wingperson of the actor (the dater); only the actor updates. The suggested_by /
    # self-decision distinction is enforced in the decisions actions, not the floor.
    RLSScopedMixin(
        read=Owner("actor_id") | Owner("recipient_id") | Owner("suggested_by"),
        edit={"INSERT": OwnerOrWinger("actor_id"), "UPDATE": Owner("actor_id")},
    ),
):
    __tablename__ = "decisions"

    # SQL: not null references profiles(id) on delete cascade
    actor_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # `state` (PENDING|APPROVED|DECLINED) is the canonical lifecycle column added by
    # StateMachineMixin. A winger suggestion lands in PENDING until the dater acts; a
    # direct like is created APPROVED; a pass / winger-decline-for-dater is DECLINED.
    # the winger who suggested this card — SQL: references profiles(id) on delete set null
    suggested_by: Mapped[Sqid | None] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    note: Mapped[str | None] = mapped_column(sa.Text, nullable=True)

    __table_args__ = (
        sa.UniqueConstraint("actor_id", "recipient_id", name="unique_actor_recipient"),
        sa.CheckConstraint("actor_id <> recipient_id", name="no_self_decision"),
    )
