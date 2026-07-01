from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.photos.enums import PhotoApprovalState
from app.platform.base.rls import Authenticated, OwnerOrWinger, RLSScopedMixin
from app.platform.state_machine.models import StateMachineMixin
from app.utils.sqids import Sqid, SqidType


class ProfilePhoto(
    StateMachineMixin(state_enum=PhotoApprovalState, initial_state=PhotoApprovalState.PENDING),
    # Read floor coarsened to "any authenticated actor" (discover/matches render
    # other daters' photos); approval/active filtering lives in the app query layer.
    # Writes stay owner + active wingperson (the dater's winger curates photos).
    RLSScopedMixin(read=Authenticated, edit=OwnerOrWinger("owner_id")),
):
    __tablename__ = "profile_photos"

    # SQL: not null references dating_profiles(id) on delete cascade
    dating_profile_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("dating_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized owner (the dating profile's dater) carried on the row: the RLS
    # floor + every action's ownership check compare it directly instead of joining
    # through dating_profiles. Immutable — a photo's owning dater never changes.
    owner_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SQL: references profiles(id) on delete set null -- null = self-uploaded
    suggester_id: Mapped[Sqid | None] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="SET NULL"),
        nullable=True,
    )
    # SQL: not null references media(id) on delete cascade -- the platform Media row
    # carrying this photo's bytes + processing lifecycle (resolve its URL via MediaService).
    media_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("media.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_order: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    # Approval truth lives in `state` (PENDING|APPROVED|REJECTED, via StateMachineMixin).
    # These stay as AUDIT timestamps written by the state machine's on_enter hooks —
    # "when was this approved/rejected" for display — not the source of approval.
    approved_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True), nullable=True)

    __table_args__ = (
        # SQL: index on (dating_profile_id, display_order)
        sa.Index(
            "ix_profile_photos_dating_profile_id_display_order",
            "dating_profile_id",
            "display_order",
        ),
        # SQL: index on (suggester_id) where suggester_id is not null
        sa.Index(
            "ix_profile_photos_suggester_id",
            "suggester_id",
            postgresql_where=sa.text("suggester_id IS NOT NULL"),
        ),
    )
