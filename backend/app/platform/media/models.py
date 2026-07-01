from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.rls_mixins import WingpersonScopedMixin
from app.platform.media.enums import MediaState
from app.platform.state_machine.models import StateMachineMixin


class Media(
    StateMachineMixin(state_enum=MediaState, initial_state=MediaState.PENDING),
    WingpersonScopedMixin,
    owner_column="owner_id",
):
    """An uploaded media object and its processing lifecycle.

    The owner (and their active wingperson) get DIRECT row access via the
    WingpersonScopedMixin policy keyed on `owner_id` — they manage their own media.
    Cross-user viewing (a matched dater seeing an approved photo) is NOT granted
    here; the photos domain authorizes visibility and then resolves the URL in
    system mode (see `MediaService.resolve_urls_system`).
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
