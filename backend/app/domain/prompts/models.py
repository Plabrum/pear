import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.prompts.enums import ApprovalState
from app.platform.base.models import BaseDBModel
from app.platform.base.rls import Authenticated, Owner, RLSScopedMixin, System
from app.platform.state_machine.models import StateMachineMixin
from app.utils.sqids import Sqid, SqidType


class PromptTemplate(BaseDBModel, RLSScopedMixin(read=Authenticated, edit=System)):
    __tablename__ = "prompt_templates"

    # question text not null
    question: Mapped[str] = mapped_column(sa.Text, nullable=False)


# Read floor coarsened to "any authenticated actor" (discover/matches render other
# daters' prompts); business visibility lives in the app query layer. Writes owner-only.
class ProfilePrompt(BaseDBModel, RLSScopedMixin(read=Authenticated, edit=Owner("owner_id"))):
    __tablename__ = "profile_prompts"

    # dating_profile_id not null references dating_profiles(id) on delete cascade
    dating_profile_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("dating_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized owner (the dating profile's dater) carried on the row: the RLS
    # floor + the delete check compare it directly instead of joining through
    # dating_profiles. Immutable — a prompt's owning dater never changes.
    owner_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # prompt_template_id not null references prompt_templates(id)
    prompt_template_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("prompt_templates.id"),
        nullable=False,
    )
    # answer text not null
    answer: Mapped[str] = mapped_column(sa.Text, nullable=False)

    template: Mapped[PromptTemplate] = relationship(lazy="raise")
    responses: Mapped[list["PromptResponse"]] = relationship(
        back_populates="profile_prompt",
        lazy="raise",
    )


class PromptResponse(
    StateMachineMixin(state_enum=ApprovalState, initial_state=ApprovalState.PENDING),
    # Read floor coarsened to "any authenticated actor" (discover surfaces winger
    # commentary on a candidate's prompts to the swiper, who is neither the author
    # nor the profile owner) — mirrors ProfilePhoto's identical shape. Approval
    # filtering lives in the app query layer (only APPROVED responses are ever
    # selected for a non-party reader), not in the RLS floor. Writes stay
    # party-scoped: author inserts, only the profile owner updates (approval).
    RLSScopedMixin(
        read=Authenticated,
        edit={"INSERT": Owner("user_id"), "UPDATE": Owner("profile_owner_id")},
    ),
):
    __tablename__ = "prompt_responses"

    # user_id not null references profiles(id) on delete cascade -- the author
    user_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Denormalized owner (the dater who owns the responded-to prompt's profile),
    # distinct from `user_id` (the author). Lets the RLS floor + the approve/delete
    # checks compare the profile owner directly instead of joining two hops.
    profile_owner_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # profile_prompt_id not null references profile_prompts(id) on delete cascade
    profile_prompt_id: Mapped[Sqid] = mapped_column(
        SqidType,
        sa.ForeignKey("profile_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # message text not null
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # Approval lifecycle (PENDING|APPROVED|REJECTED) is the canonical `state` column
    # added by StateMachineMixin — driven through ApprovePromptResponse's transition.

    profile_prompt: Mapped[ProfilePrompt] = relationship(
        back_populates="responses",
        lazy="raise",
    )
