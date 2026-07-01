"""DatingProfile model — a dater's configurable dating profile.

Ports `public.dating_profiles` from 20260228000000_schema.sql (with the city enum
collapsed to Boston / New York by 20260301000000_update_city_enum.sql).

Deviations from the SQL (per the migration plan):
  * The table's own `id` UUID PK + `created_at`/`updated_at` are inherited from
    BaseDBModel (the SQL declared them ad-hoc; the set_updated_at trigger is not
    ported — onupdate=now() on BaseDBModel.updated_at covers it).
  * Enum columns / arrays are TEXT (TextEnum), not Postgres native enums.
  * `user_id` is a real FK to profiles.id with a UNIQUE constraint (one dating
    profile per user), matching the SQL `unique references public.profiles (id)`.
"""

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.dating_profiles.enums import City, DatingStatus, Interest, Religion
from app.domain.profiles.enums import Gender
from app.platform.base.models import BaseDBModel
from app.utils.textenum import TextEnum


class DatingProfile(BaseDBModel):
    __tablename__ = "dating_profiles"

    # one dating profile per user — SQL: not null unique references profiles(id)
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    bio: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # gender[] not null default '{}'
    interested_gender: Mapped[list[Gender]] = mapped_column(
        ARRAY(TextEnum(Gender)),
        nullable=False,
        server_default="{}",
    )
    age_from: Mapped[int] = mapped_column(sa.Integer, nullable=False)
    age_to: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    # religion not null in the SQL
    religion: Mapped[Religion] = mapped_column(TextEnum(Religion), nullable=False)
    # religious_preference nullable (null = no preference)
    religious_preference: Mapped[Religion | None] = mapped_column(TextEnum(Religion), nullable=True)
    # interest[] not null default '{}'
    interests: Mapped[list[Interest]] = mapped_column(
        ARRAY(TextEnum(Interest)),
        nullable=False,
        server_default="{}",
    )
    city: Mapped[City] = mapped_column(TextEnum(City), nullable=False)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=True, server_default=sa.true())
    dating_status: Mapped[DatingStatus] = mapped_column(
        TextEnum(DatingStatus),
        nullable=False,
        default=DatingStatus.OPEN,
        server_default=DatingStatus.OPEN.name,
    )
