"""Throwaway sample model — proves the platform abstractions wire together.

`SampleWidget` exercises:
  * `BaseDBModel` (UUID PK + audit + soft-delete columns)
  * `StateMachineMixin` (indexed TextEnum `state` column)
  * `UserScopedMixin` (registers a generic user-scoped RLS PGPolicy + RLS enable)

It lives under `tests/fixtures/` (NOT `app/domain/`) so the prod model registry
and Alembic autogenerate never discover it — the `sample_widgets` table exists
only in the TEST database, created by the `setup_sample_table` fixture in
`tests/fixtures/database.py`. Importing this module attaches the mapper to
`BaseDBModel.metadata`, which is what makes that table creation possible.
"""

from enum import StrEnum, auto
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.rls_mixins import UserScopedMixin
from app.platform.state_machine.models import StateMachineMixin


class SampleStatus(StrEnum):
    """Two-state lifecycle for the sample widget."""

    DRAFT = auto()
    ACTIVE = auto()


class SampleWidget(
    StateMachineMixin(state_enum=SampleStatus, initial_state=SampleStatus.DRAFT),
    UserScopedMixin,
):
    __tablename__ = "sample_widgets"

    # Owning user — `UserScopedMixin` registers the RLS policy that reads this.
    # Soft reference only (no FK): kept decoupled from the prod schema.
    user_id: Mapped[UUID] = mapped_column(sa.Uuid, index=True, nullable=False)

    name: Mapped[str] = mapped_column(sa.Text, nullable=False, default="untitled")
