import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.profiles.models import Profile
from app.platform.base.models import BaseDBModel
from app.utils.sqids import Sqid, SqidType


class ProfileReport(BaseDBModel):
    __tablename__ = "profile_reports"

    # SQL: reporter_id uuid not null references auth.users(id) on delete cascade
    reporter_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # SQL: reported_id uuid not null references auth.users(id) on delete cascade
    reported_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(sa.Text, nullable=False)

    reporter: Mapped[Profile] = relationship(
        Profile,
        foreign_keys=[reporter_id],
        lazy="raise",
    )
    reported: Mapped[Profile] = relationship(
        Profile,
        foreign_keys=[reported_id],
        lazy="raise",
    )
