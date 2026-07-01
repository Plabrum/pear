import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.rls import OwnerOrWinger, RLSScopedMixin
from app.platform.media.enums import MediaState
from app.platform.state_machine.models import StateMachineMixin
from app.utils.sqids import Sqid, SqidType

# The one genuinely-derived read: a viewer may read a media row iff they may see the
# photo backing it — owner, the photo's suggester, or an APPROVED photo on an ACTIVE
# dating profile — plus public avatars. The discover/match feeds presign other
# daters' approved photos under the viewer's OWN scope, so this runs in the request
# path (no system mode). Expressed via the raw-SQL escape so it stays on the model.
_MEDIA_READ = """
          owner_id = public.current_user_id()
          OR public.is_active_wingperson(owner_id)
          OR EXISTS (
            SELECT 1
            FROM public.profile_photos pp
            JOIN public.dating_profiles dp ON dp.id = pp.dating_profile_id
            WHERE pp.media_id = media.id
              AND (
                dp.user_id = public.current_user_id()
                OR pp.suggester_id = public.current_user_id()
                OR (dp.is_active = true AND pp.state = 'APPROVED')
              )
          )
          OR EXISTS (
            SELECT 1 FROM public.profiles p WHERE p.avatar_media_id = media.id
          )
""".strip()


class Media(
    StateMachineMixin(state_enum=MediaState, initial_state=MediaState.PENDING),
    # SELECT mirrors profile_photos visibility (derived, request-path); write floor is
    # owner + active wingperson (the winger curates the dater's media).
    RLSScopedMixin(read=_MEDIA_READ, edit=OwnerOrWinger("owner_id")),
):
    __tablename__ = "media"

    # SQL: not null references profiles(id) on delete cascade
    owner_id: Mapped[Sqid] = mapped_column(
        SqidType,
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
