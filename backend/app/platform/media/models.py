from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.media.enums import MediaState
from app.platform.state_machine.models import StateMachineMixin


class Media(
    StateMachineMixin(state_enum=MediaState, initial_state=MediaState.PENDING),
):
    """An uploaded media object and its processing lifecycle.

    Media carries BESPOKE per-command RLS policies (in `rls_policies.py`), not the
    generic WingpersonScopedMixin FOR ALL policy: SELECT mirrors profile_photos
    visibility so a viewer reads a media row iff they may see the photo backing it
    (plus avatars are public-read), while INSERT/UPDATE/DELETE stay owner + active
    wingperson. A matched viewer therefore presigns an approved photo's URL under
    their OWN scope — no system mode, no elevated read.
    """

    __tablename__ = "media"

    # SQL: not null references profiles(id) on delete cascade
    owner_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # The original upload key (what the client PUTs to via the presigned URL).
    file_key: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # The processed (re-encoded) result key; null until processing reaches READY.
    processed_key: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    mime_type: Mapped[str] = mapped_column(sa.Text, nullable=False)
    file_name: Mapped[str] = mapped_column(sa.Text, nullable=False)
