import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.base.rls import Owner, OwnerOrWinger, RLSScopedMixin
from app.utils.sqids import Sqid, SqidType


class RlsOwnedThing(BaseDBModel, RLSScopedMixin(read=Owner("user_id"), edit=Owner("user_id"))):
    """Throwaway model exercising `RLSScopedMixin` with owner-only read + write."""

    __tablename__ = "rls_owned_things"

    # Owning user — the `Owner("user_id")` scope reads this column.
    # Soft reference only (no FK): decoupled from the prod schema.
    user_id: Mapped[Sqid] = mapped_column(SqidType, index=True, nullable=False)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, default="unnamed")


class RlsWingThing(BaseDBModel, RLSScopedMixin(read=OwnerOrWinger("user_id"), edit=OwnerOrWinger("user_id"))):
    """Throwaway model exercising `RLSScopedMixin` with owner + active-winger access."""

    __tablename__ = "rls_wing_things"

    # Owning dater — must match `profiles(id)` so `is_active_wingperson(user_id)`
    # resolves an ACTIVE contact. Soft reference only (no FK) for the test schema.
    user_id: Mapped[Sqid] = mapped_column(SqidType, index=True, nullable=False)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, default="unnamed")
