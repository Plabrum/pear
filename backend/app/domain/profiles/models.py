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
