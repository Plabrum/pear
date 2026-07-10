from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.platform.base.models import BaseDBModel
from app.platform.updates.enums import RolloutStatus, UpdateChannel, UpdatePlatform
from app.utils.textenum import TextEnum

# No RLS on this table — the same call the `profiles` identity table already made
# (see `20260629_1457_drop_rls_on_profiles_identity_table_e74b9f4587a7`): both
# routes that touch `app_updates` (`/updates/v2/manifest`, `/updates/publish`) are
# unauthenticated and root-mounted, outside the auth-gated `/api` — there is no
# per-request actor (`app.user_id`) to scope a policy against, the same
# chicken-and-egg shape that justified dropping RLS on `profiles`. `pear_app`'s
# blanket table grant (`rls_grants.py`'s `GRANT ... ON ALL TABLES`) already covers
# CRUD here; the real security floor is the bearer-token guard on
# `POST /updates/publish` (`requires_updates_publish_token`), not a DB policy.


class AppUpdate(BaseDBModel):
    """One published OTA update for a (runtime_version, channel, platform) tuple.

    The source of truth the v2 manifest route (`app/platform/updates/routes.py`)
    serves "what's the current update" from.
    """

    __tablename__ = "app_updates"
    __table_args__ = (
        sa.Index(
            "ix_app_updates_lookup",
            "runtime_version",
            "channel",
            "platform",
            "rollout",
            "created_at",
        ),
    )

    # A dedicated RFC-4122 UUID, distinct from the table's Sqid-encoded integer PK
    # (`BaseDBModel.id`, kept for consistency with every other table). The v2
    # manifest's `update_uuid` field and the `current_update_id` query param are
    # both wire-format UUIDs — a Sqid isn't one — so this column exists purely to
    # satisfy that wire contract.
    update_uuid: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        server_default=sa.text("gen_random_uuid()"),
        unique=True,
        nullable=False,
    )
    runtime_version: Mapped[str] = mapped_column(sa.Text, nullable=False, index=True)
    channel: Mapped[UpdateChannel] = mapped_column(TextEnum(UpdateChannel), nullable=False, index=True)
    platform: Mapped[UpdatePlatform] = mapped_column(TextEnum(UpdatePlatform), nullable=False, index=True)
    # {"key": md5, "contentType": ..., "url": <CloudFront url>, "hash": base64url-sha256}
    # — populated verbatim by the publish step; the serve route passes it through.
    launch_asset: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # [{"key": md5, "contentType": ..., "url": ..., "hash": ..., "fileExtension": ...}, ...]
    assets: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    rollout: Mapped[RolloutStatus] = mapped_column(
        TextEnum(RolloutStatus),
        server_default="LIVE",
        nullable=False,
        index=True,
    )
    # Staged-rollout percentage (0-100); NULL means "fully live" (no gating beyond
    # `rollout`). Reserved for a future percentage-gated lookup — not yet
    # consulted by the manifest route's simple latest-row lookup.
    rollout_pct: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
