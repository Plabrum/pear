from enum import StrEnum, auto

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.rls import Authenticated, Owner, RLSScopedMixin
from app.platform.state_machine.models import StateMachineMixin
from app.utils.sqids import Sqid, SqidType


class SampleStatus(StrEnum):
    """Two-state lifecycle for the sample widget."""

    DRAFT = auto()
    ACTIVE = auto()


class SampleWidget(
    StateMachineMixin(state_enum=SampleStatus, initial_state=SampleStatus.DRAFT),
    RLSScopedMixin(read=Authenticated, edit=Owner("user_id")),
):
    __tablename__ = "sample_widgets"

    # Owning user — the `Owner("user_id")` write scope reads this.
    # Soft reference only (no FK): kept decoupled from the prod schema.
    user_id: Mapped[Sqid] = mapped_column(SqidType, index=True, nullable=False)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, default="untitled")
