from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.queue.enums import TaskStatus
from app.utils.textenum import TextEnum


class Task(BaseDBModel):
    """Tracking row for an enqueued SAQ job (upserted by before/after_process hooks)."""

    __tablename__ = "tasks"

    job_key: Mapped[str] = mapped_column(sa.Text, index=True, unique=True)
    queue: Mapped[str] = mapped_column(sa.Text)
    task_name: Mapped[str] = mapped_column(sa.Text, index=True)
    status: Mapped[TaskStatus] = mapped_column(TextEnum(TaskStatus))
    started_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(sa.DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(sa.Text)
