from __future__ import annotations

from sqlalchemy import asc, case, desc, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.matches.models import Match
from app.domain.messages.models import Message
from app.domain.messages.transformers import ConversationRow, MessageRow
from app.domain.profiles.models import Profile
from app.utils.sqids import Sqid


async def fetch_push_token(db: AsyncSession, user_id: Sqid) -> str | None:
    return (await db.execute(select(Profile.push_token).where(Profile.id == user_id).limit(1))).scalar_one_or_none()


async def is_viewer_in_match(db: AsyncSession, viewer_id: Sqid, match_id: Sqid) -> bool:
    """The viewer is a participant AND the other participant isn't deactivated.

    404s an already-known match once the other party deactivates, so a direct
    thread-by-match_id lookup doesn't stay readable.
    """
    other_id_expr = case(
        (Match.user_a_id == viewer_id, Match.user_b_id),
        else_=Match.user_a_id,
    )
    row = (
        await db.execute(
            select(Match.id)
            .outerjoin(Profile, Profile.id == other_id_expr)
            .where(
                Match.id == match_id,
                or_(Match.user_a_id == viewer_id, Match.user_b_id == viewer_id),
                or_(Profile.id.is_(None), Profile.deactivated_at.is_(None)),
            )
            .limit(1)
        )
    ).first()
    return row is not None


async def get_match_peers(db: AsyncSession, match_id: Sqid) -> tuple[Sqid, Sqid] | None:
    row = (await db.execute(select(Match.user_a_id, Match.user_b_id).where(Match.id == match_id).limit(1))).first()
    if row is None:
        return None
    return row.user_a_id, row.user_b_id


async def fetch_messages_for_match(db: AsyncSession, match_id: Sqid, limit: int, offset: int) -> list[MessageRow]:
    rows = (
        await db.execute(
            select(
                Message.id,
                Message.match_id,
                Message.sender_id,
                Message.body,
                Message.is_read,
                Message.created_at,
                Profile.chosen_name,
            )
            .outerjoin(Profile, Profile.id == Message.sender_id)
            .where(Message.match_id == match_id)
            .order_by(asc(Message.created_at))
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return [
        MessageRow(
            id=r.id,
            match_id=r.match_id,
            sender_id=r.sender_id,
            body=r.body,
            is_read=r.is_read,
            created_at=r.created_at,
            sender_chosen_name=r.chosen_name,
        )
        for r in rows
    ]


async def fetch_conversations(db: AsyncSession, viewer_id: Sqid) -> list[ConversationRow]:
    other_id_expr = case(
        (Match.user_a_id == viewer_id, Match.user_b_id),
        else_=Match.user_a_id,
    )

    # "Last message in this match" — all five columns from one LEFT JOIN LATERAL
    # (`... where match_id = ? order by created_at desc limit 1`), backed by
    # `ix_messages_match_id_created_at`. Replaces five identical correlated probes.
    last_msg = (
        select(
            Message.id.label("last_message_id"),
            Message.body.label("last_message_body"),
            Message.sender_id.label("last_message_sender_id"),
            Message.is_read.label("last_message_is_read"),
            Message.created_at.label("last_message_created_at"),
        )
        .where(Message.match_id == Match.id)
        .order_by(desc(Message.created_at))
        .limit(1)
        .lateral("last_message")
    )

    unread_count = (
        select(func.count())
        .where(
            Message.match_id == Match.id,
            Message.sender_id != viewer_id,
            Message.is_read.is_(False),
        )
        .correlate(Match)
        .scalar_subquery()
    )

    order_expr = func.coalesce(last_msg.c.last_message_created_at, Match.created_at)

    other = aliased(Profile)
    other_join = case(
        (Match.user_a_id == viewer_id, Match.user_b_id),
        else_=Match.user_a_id,
    )

    rows = (
        await db.execute(
            select(
                Match.id.label("match_id"),
                Match.created_at.label("match_created_at"),
                other_id_expr.label("other_user_id"),
                other.chosen_name.label("other_chosen_name"),
                last_msg.c.last_message_id.label("last_message_id"),
                last_msg.c.last_message_body.label("last_message_body"),
                last_msg.c.last_message_sender_id.label("last_message_sender_id"),
                last_msg.c.last_message_is_read.label("last_message_is_read"),
                last_msg.c.last_message_created_at.label("last_message_created_at"),
                unread_count.label("unread_count"),
            )
            .select_from(Match)
            .outerjoin(other, other.id == other_join)
            .outerjoin(last_msg, true())
            .where(
                or_(Match.user_a_id == viewer_id, Match.user_b_id == viewer_id),
                or_(other.id.is_(None), other.deactivated_at.is_(None)),
            )
            .order_by(desc(order_expr))
        )
    ).all()

    return [
        ConversationRow(
            match_id=r.match_id,
            match_created_at=r.match_created_at,
            other_user_id=r.other_user_id,
            other_chosen_name=r.other_chosen_name,
            last_message_id=r.last_message_id,
            last_message_body=r.last_message_body,
            last_message_sender_id=r.last_message_sender_id,
            last_message_is_read=r.last_message_is_read,
            last_message_created_at=r.last_message_created_at,
            unread_count=r.unread_count,
        )
        for r in rows
    ]


async def insert_message(db: AsyncSession, match_id: Sqid, sender_id: Sqid, body: str) -> MessageRow:
    message = Message(match_id=match_id, sender_id=sender_id, body=body)
    db.add(message)
    await db.flush()

    sender_name = (
        await db.execute(select(Profile.chosen_name).where(Profile.id == sender_id).limit(1))
    ).scalar_one_or_none()

    return MessageRow(
        id=message.id,
        match_id=message.match_id,
        sender_id=message.sender_id,
        body=message.body,
        is_read=message.is_read,
        created_at=message.created_at,
        sender_chosen_name=sender_name,
    )


async def mark_messages_read(db: AsyncSession, match_id: Sqid, viewer_id: Sqid) -> int:
    """Mark inbound (not-sent-by-viewer) unread messages as read; return the count.

    RLS already restricts the rows to matches the viewer is party to; the
    `sender_id != viewer` clause keeps a viewer from flipping their own outbound
    messages.
    """
    rows = (
        (
            await db.execute(
                select(Message).where(
                    Message.match_id == match_id,
                    Message.is_read.is_(False),
                    Message.sender_id != viewer_id,
                )
            )
        )
        .scalars()
        .all()
    )
    for message in rows:
        message.is_read = True
    if rows:
        await db.flush()
    return len(rows)
