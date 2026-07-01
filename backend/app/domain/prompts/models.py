from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.platform.base.models import BaseDBModel


class PromptTemplate(BaseDBModel):
    __tablename__ = "prompt_templates"

    # question text not null
    question: Mapped[str] = mapped_column(sa.Text, nullable=False)


class ProfilePrompt(BaseDBModel):
    __tablename__ = "profile_prompts"

    # dating_profile_id not null references dating_profiles(id) on delete cascade
    dating_profile_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("dating_profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # prompt_template_id not null references prompt_templates(id)
    prompt_template_id: Mapped[UUID] = mapped_column(
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


class PromptResponse(BaseDBModel):
    __tablename__ = "prompt_responses"

    # user_id not null references profiles(id) on delete cascade
    user_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
    )
    # profile_prompt_id not null references profile_prompts(id) on delete cascade
    profile_prompt_id: Mapped[UUID] = mapped_column(
        sa.ForeignKey("profile_prompts.id", ondelete="CASCADE"),
        nullable=False,
    )
    # message text not null
    message: Mapped[str] = mapped_column(sa.Text, nullable=False)
    # is_approved bool not null default false
    is_approved: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )
    # is_rejected boolean not null default false
    is_rejected: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        default=False,
        server_default=sa.false(),
    )

    profile_prompt: Mapped[ProfilePrompt] = relationship(
        back_populates="responses",
        lazy="raise",
    )
