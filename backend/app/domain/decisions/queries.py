from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Row, and_, desc, exists, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.decisions.transformers import SuggestionRow
from app.domain.matches.models import Match
from app.domain.profiles.models import Profile

# ── Decision writes ───────────────────────────────────────────────────────────


async def upsert_direct_decision(
    db: AsyncSession,
    actor_id: UUID,
    recipient_id: UUID,
    decision: DecisionType,
) -> None:
    """Direct like/pass: upsert the actor's decision on the recipient.

    Upserts on (actor_id, recipient_id). Match formation is the action's
    on-approve side-effect (see `actions.py`).
    """
    stmt = (
        pg_insert(Decision)
        .values(actor_id=actor_id, recipient_id=recipient_id, decision=decision)
        .on_conflict_do_update(
            constraint="unique_actor_recipient",
            set_={"decision": pg_insert(Decision).excluded.decision},
        )
        .returning(Decision)
    )
    # populate_existing syncs the identity map so a same-transaction entity re-read
    # sees the upserted decision (RETURNING refreshes the row we just wrote).
    await db.execute(stmt, execution_options={"populate_existing": True})
    await db.flush()


async def insert_wing_suggestion(
    db: AsyncSession,
    dater_id: UUID,
    recipient_id: UUID,
    winger_id: UUID,
    note: str | None,
    decision: DecisionType | None,
) -> bool:
    """Winger creates a suggestion row on the dater's behalf.

    `decision`:
      * None       -> normal suggestion the dater can act on (with optional note).
      * 'declined' -> winger declines the recipient on the dater's behalf.

    On conflict, does nothing: if the (actor, recipient) pair already exists (the
    dater already decided on / was already suggested this recipient), no row is
    written. Returns True only on a genuinely new insert.
    """
    stmt = (
        pg_insert(Decision)
        .values(
            actor_id=dater_id,
            recipient_id=recipient_id,
            suggested_by=winger_id,
            decision=decision,
            note=note,
        )
        .on_conflict_do_nothing(constraint="unique_actor_recipient")
        .returning(Decision.id)
    )
    inserted = (await db.execute(stmt)).scalar_one_or_none()
    await db.flush()
    return inserted is not None


# ── Mutual-match lookup + match formation ─────────────────────────────────────


async def find_mutual_match(db: AsyncSession, user_a: UUID, user_b: UUID) -> Match | None:
    """Look up the matches row for a pair, regardless of who is user_a vs user_b.

    `matches` enforces user_a_id < user_b_id, so we order before querying.
    """
    lo, hi = (user_a, user_b) if str(user_a) < str(user_b) else (user_b, user_a)
    return (
        await db.execute(select(Match).where(and_(Match.user_a_id == lo, Match.user_b_id == hi)).limit(1))
    ).scalar_one_or_none()


async def both_sides_approved(db: AsyncSession, user_a: UUID, user_b: UUID) -> bool:
    """True when BOTH directions of the decision are 'approved' (mutual like).

    This is the condition checked before inserting a match row.
    """
    rows = (
        await db.execute(
            select(Decision.actor_id, Decision.recipient_id).where(
                and_(
                    Decision.decision == DecisionType.APPROVED,
                    Decision.actor_id.in_([user_a, user_b]),
                    Decision.recipient_id.in_([user_a, user_b]),
                )
            )
        )
    ).all()
    pairs = {(a, r) for a, r in rows}
    return (user_a, user_b) in pairs and (user_b, user_a) in pairs


# ── Authorization + push lookups ──────────────────────────────────────────────


async def is_active_wingperson(db: AsyncSession, dater_id: UUID, winger_id: UUID) -> bool:
    """True when `winger_id` is an ACTIVE wingperson for `dater_id`."""
    row = (
        await db.execute(
            select(Contact.id)
            .where(
                and_(
                    Contact.user_id == dater_id,
                    Contact.winger_id == winger_id,
                    Contact.wingperson_status == WingpersonStatus.ACTIVE,
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return row is not None


async def push_tokens_for(db: AsyncSession, user_ids: list[UUID]) -> list[str]:
    """Non-null Expo push tokens for the given users."""
    if not user_ids:
        return []
    rows = (await db.execute(select(Profile.push_token).where(Profile.id.in_(user_ids)))).all()
    return [token for (token,) in rows if token is not None]


async def dater_push_and_winger_name(
    db: AsyncSession, dater_id: UUID, winger_id: UUID
) -> tuple[str | None, str | None]:
    """Return (dater push token, winger chosen name) for the suggestion push."""
    rows = (
        await db.execute(
            select(Profile.id, Profile.push_token, Profile.chosen_name).where(Profile.id.in_([dater_id, winger_id]))
        )
    ).all()
    dater_token: str | None = None
    winger_name: str | None = None
    for pid, token, name in rows:
        if pid == dater_id:
            dater_token = token
        if pid == winger_id:
            winger_name = name
    return dater_token, winger_name


# ── Pending-suggestions read ──────────────────────────────────────────────────


async def fetch_pending_suggestions(
    db: AsyncSession, actor_id: UUID
) -> Sequence[Row[tuple[UUID, UUID, str | None, Any, UUID | None, str | None]]]:
    """Pending winger suggestions awaiting the viewer (actor_id).

    A pending suggestion is a decision row where `decision IS NULL` and
    `suggested_by IS NOT NULL`, newest first. Returns
    (id, recipient_id, note, created_at, winger_id, winger_name) tuples; the route
    maps them through `row_to_pending_suggestion`.
    """
    winger = aliased(Profile)
    rows = (
        await db.execute(
            select(
                Decision.id,
                Decision.recipient_id,
                Decision.note,
                Decision.created_at,
                Decision.suggested_by,
                winger.chosen_name,
            )
            .outerjoin(winger, winger.id == Decision.suggested_by)
            .where(
                and_(
                    Decision.actor_id == actor_id,
                    Decision.decision.is_(None),
                    Decision.suggested_by.is_not(None),
                )
            )
            .order_by(desc(Decision.created_at))
        )
    ).all()
    return rows


# ── Suggestions I made as a winger (the people-activity read) ──────────────────


async def fetch_my_suggestions(db: AsyncSession, winger_id: UUID, limit: int) -> list[SuggestionRow]:
    """Cards the winger suggested + whether each became a match, newest first.

    Every decision row the winger authored (`suggested_by = winger_id`), joined to
    the dater (actor) and recipient profile names, with a correlated EXISTS that
    reports whether a match now joins the actor and recipient (in either id
    ordering).
    """
    dater = aliased(Profile)
    recipient = aliased(Profile)

    match_exists_expr = exists(
        select(Match.id).where(
            or_(
                and_(
                    Match.user_a_id == Decision.actor_id,
                    Match.user_b_id == Decision.recipient_id,
                ),
                and_(
                    Match.user_a_id == Decision.recipient_id,
                    Match.user_b_id == Decision.actor_id,
                ),
            )
        )
    )

    rows = (
        await db.execute(
            select(
                Decision.id,
                Decision.decision,
                match_exists_expr,
                Decision.actor_id,
                dater.chosen_name,
                recipient.chosen_name,
                Decision.created_at,
            )
            .join(dater, dater.id == Decision.actor_id)
            .join(recipient, recipient.id == Decision.recipient_id)
            .where(
                and_(
                    Decision.suggested_by.is_not(None),
                    Decision.suggested_by == winger_id,
                )
            )
            .order_by(desc(Decision.created_at))
            .limit(limit)
        )
    ).all()

    return [
        SuggestionRow(
            id=decision_id,
            decision=decision,
            has_match=bool(has_match),
            dater_id=dater_id,
            dater_name=dater_name,
            recipient_name=recipient_name,
            created_at=created_at,
        )
        for (
            decision_id,
            decision,
            has_match,
            dater_id,
            dater_name,
            recipient_name,
            created_at,
        ) in rows
    ]
