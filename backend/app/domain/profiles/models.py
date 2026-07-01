"""Profile model — the identity anchor for every user (dater or winger).

Ports `public.profiles` from the Supabase schema:
  * 20260227000000_init.sql      — base table (+ avatar_url)
  * 20260228000000_schema.sql    — chosen_name/last_name/phone_number/date_of_birth/
                                    gender/role/push_token columns

Key deviations from the SQL (per the migration plan):
  * `id` is the inherited UUID PK from BaseDBModel — NO ForeignKey to auth.users.
    Self-hosted auth owns identity from Phase 4; profiles.id is a plain UUID.
  * `created_at`/`updated_at` are inherited from BaseDBModel (the SQL's ad-hoc
    `updated_at` / `created_at` columns are subsumed; soft-delete `deleted_at` is
    additive and harmless).
  * Enum columns are TEXT via `TextEnum`, not Postgres native enums.
  * The handle_new_user / on_auth_user_created trigger is NOT ported (Phase 4 auth).
"""

from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.profiles.enums import Gender, UserRole
from app.platform.base.models import BaseDBModel
from app.utils.textenum import TextEnum


class Profile(BaseDBModel):
    __tablename__ = "profiles"

    chosen_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    last_name: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    phone_number: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    date_of_birth: Mapped[date | None] = mapped_column(sa.Date, nullable=True)
    # Nullable in the SQL; used by the discover gender filter once set.
    gender: Mapped[Gender | None] = mapped_column(TextEnum(Gender), nullable=True)
    # NOT NULL default 'dater' in the SQL.
    role: Mapped[UserRole] = mapped_column(
        TextEnum(UserRole),
        nullable=False,
        default=UserRole.DATER,
        server_default=UserRole.DATER.name,
    )
    avatar_url: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    # Expo push token; set after the user grants notification permission.
    push_token: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
