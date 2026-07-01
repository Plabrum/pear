from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from app.platform.media.enums import MediaState
from app.platform.media.models import Media


def servable_key_expr(media_id_col: Any) -> ColumnElement[Any]:
    """Correlated scalar subquery: the best servable key for `media_id_col` (or NULL).

    Mirrors `MediaService._servable_key`: the processed key once a Media is READY
    and has one, otherwise the original `file_key`. Lets a SQL aggregate hand a
    plain key to `BaseMediaClient.presign_download` exactly as a raw column once did.

    `media_id_col` is the foreign-key column (an ORM mapped attribute or alias) — typed
    `Any` because SQLAlchemy resolves those at runtime, matching the alias columns
    elsewhere in the query layer.
    """
    return (
        select(
            case(
                (
                    (Media.state == MediaState.READY) & Media.processed_key.is_not(None),
                    Media.processed_key,
                ),
                else_=Media.file_key,
            )
        )
        .where(Media.id == media_id_col)
        .limit(1)
        .scalar_subquery()
    )


def public_key_expr(media_id_col: Any) -> ColumnElement[Any]:
    """Correlated scalar subquery: an avatar's public key for `media_id_col` (or NULL).

    Avatars resolve to the processed (public-read) object once READY; until then
    there is no public object, so NULL. Feeds `BaseMediaClient.public_url`.
    `media_id_col` is typed `Any` (a runtime-resolved ORM/alias column).
    """
    return (
        select(Media.processed_key)
        .where(
            Media.id == media_id_col,
            Media.state == MediaState.READY,
            Media.processed_key.is_not(None),
        )
        .limit(1)
        .scalar_subquery()
    )


async def fetch_media(db: AsyncSession, media_id: UUID) -> Media | None:
    """A single media row by id, subject to the caller's RLS scope."""
    return (await db.execute(select(Media).where(Media.id == media_id).limit(1))).scalar_one_or_none()


async def fetch_media_by_ids(db: AsyncSession, media_ids: Sequence[UUID]) -> list[Media]:
    """Media rows for the given ids, subject to the caller's RLS scope.

    Used by the system-mode resolve: the photos domain authorizes visibility, then
    reads these rows under `app.is_system_mode = true` to presign their URLs.
    """
    if not media_ids:
        return []
    rows = (await db.execute(select(Media).where(Media.id.in_(media_ids)))).scalars().all()
    return list(rows)
