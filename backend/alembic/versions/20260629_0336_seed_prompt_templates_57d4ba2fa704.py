"""seed prompt templates

Revision ID: 57d4ba2fa704
Revises: 41e71251b338
Create Date: 2026-06-29 03:36:48.180404+00:00

Reference-data migration: populates `prompt_templates` with the profile prompt
questions. Keeping these as a data migration (not a dev seed script) means every
environment — local, CI, prod — gets the same template rows deterministically as
part of `alembic upgrade head`.

`profile_prompts.prompt_template_id` is a NOT NULL FK to this table, so the app
cannot create a single dater prompt until these rows exist.

The PK `id` is an int identity/serial assigned by Postgres; `created_at`/
`updated_at` fall back to the table's `now()` server defaults.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "57d4ba2fa704"
down_revision: str | None = "41e71251b338"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PROMPT_QUESTIONS: list[str] = [
    "The way to my heart is…",
    "A perfect Sunday looks like…",
    "My love language is…",
    "I get way too excited about…",
    "The most spontaneous thing I've done…",
    "Two truths and a lie…",
    "My friends would describe me as…",
    "I'm looking for someone who…",
    "Unpopular opinion I hold…",
    "My go-to karaoke song…",
]


def upgrade() -> None:
    # `id` is an autoincrement int PK assigned by Postgres; omit it so the serial
    # sequence fills it. `created_at`/`updated_at` use their `now()` defaults.
    bind = op.get_bind()
    bind.execute(
        sa.text("INSERT INTO prompt_templates (question) VALUES (:question)"),
        [{"question": question} for question in PROMPT_QUESTIONS],
    )


def downgrade() -> None:
    # Remove exactly the rows this migration seeded.
    bind = op.get_bind()
    bind.execute(
        sa.text("DELETE FROM prompt_templates WHERE question = ANY(:questions)"),
        {"questions": PROMPT_QUESTIONS},
    )
