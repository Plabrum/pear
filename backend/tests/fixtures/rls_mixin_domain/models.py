from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.base.rls_mixins import UserScopedMixin, WingpersonScopedMixin


class RlsOwnedThing(BaseDBModel, UserScopedMixin):
    """Throwaway model exercising `UserScopedMixin` (owner-only access)."""

    __tablename__ = "rls_owned_things"

    # Owning user — `UserScopedMixin` registers the policy that reads this column.
    # Soft reference only (no FK): decoupled from the prod schema.
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, index=True, nullable=False)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, default="unnamed")


class RlsWingThing(BaseDBModel, WingpersonScopedMixin):
    """Throwaway model exercising `WingpersonScopedMixin` (owner + active winger)."""

    __tablename__ = "rls_wing_things"

    # Owning dater — must match `profiles(id)` so `is_active_wingperson(user_id)`
    # resolves an ACTIVE contact. Soft reference only (no FK) for the test schema.
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, index=True, nullable=False)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, default="unnamed")
