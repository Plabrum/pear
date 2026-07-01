from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Row, and_, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
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
    existing = (
        await db.execute(
            select(Decision)
            .where(
                and_(
                    Decision.actor_id == actor_id,
                    Decision.recipient_id == recipient_id,
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if existing is not None:
        existing.decision = decision
    else:
        db.add(Decision(actor_id=actor_id, recipient_id=recipient_id, decision=decision))
    await db.flush()


async def act_on_pending_suggestion(
    db: AsyncSession,
    actor_id: UUID,
    recipient_id: UUID,
    decision: DecisionType,
) -> bool:
    """Approve/decline a winger's pending suggestion.

    Constrained to rows the caller owns (actor_id) AND where `decision IS NULL`,
    so a finalised decision can't be overwritten through this path. Returns True
    when a pending row was found and updated.
    """
    row = (
        await db.execute(
            select(Decision)
            .where(
                and_(
                    Decision.actor_id == actor_id,
                    Decision.recipient_id == recipient_id,
                    Decision.decision.is_(None),
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.decision = decision
    await db.flush()
    return True


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
    existing = (
        await db.execute(
            select(Decision.id)
            .where(
                and_(
                    Decision.actor_id == dater_id,
                    Decision.recipient_id == recipient_id,
                )
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return False

    db.add(
        Decision(
            actor_id=dater_id,
            recipient_id=recipient_id,
            suggested_by=winger_id,
            decision=decision,
            note=note,
        )
    )
    await db.flush()
    return True


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


async def create_match_system(db: AsyncSession, user_a: UUID, user_b: UUID) -> Match:
    """Insert the matches row under the honored system-mode escape.

    The `matches_insert` RLS policy is `WITH CHECK (public.is_system_mode())` — an
    ordinary user can never forge a match. We briefly enable `app.is_system_mode`
    for just this INSERT (SET LOCAL is transaction-scoped, restored immediately
    after) so the match is created as a SYSTEM operation.

    Ids are ordered to satisfy the `ordered_match_ids` CHECK (user_a_id < user_b_id).
    """
    lo, hi = (user_a, user_b) if str(user_a) < str(user_b) else (user_b, user_a)
    match = Match(user_a_id=lo, user_b_id=hi)
    db.add(match)
    # Enable the escape for the flush, then RESTORE the prior value so the rest of
    # the request keeps its original scope. In a normal request that prior value is
    # `false` (user-scoped); under the system-mode test/worker path it's `true`, so
    # we must not hardcode `false` or we'd break subsequent reads. SET LOCAL is
    # transaction-scoped and rolls back with the transaction.
    prior = (await db.execute(text("SELECT current_setting('app.is_system_mode', true)"))).scalar_one_or_none()
    await db.execute(text("SET LOCAL app.is_system_mode = true"))
    try:
        await db.flush()
    finally:
        restore = "true" if prior == "true" else "false"
        await db.execute(text(f"SET LOCAL app.is_system_mode = {restore}"))
    return match


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
