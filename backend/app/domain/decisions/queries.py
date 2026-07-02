from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from sqlalchemy import and_, desc, exists, literal, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.domain.contacts.queries import is_active_wingperson  # noqa: F401  (re-exported)
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.domain.decisions.state_machine import decision_machine
from app.domain.decisions.transformers import SuggestionRow
from app.domain.matches.models import Match
from app.domain.profiles.models import Profile
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Actor
from app.utils.sqids import Sqid, SqidType

# ── Decision writes ───────────────────────────────────────────────────────────


async def apply_dater_decision(
    db: AsyncSession,
    sm_service: StateMachineService,
    actor: Actor,
    recipient_id: Sqid,
    target_state: DecisionState,
) -> None:
    """The dater's own decision on a recipient: create it, or transition the existing row.

    A brand-new pair has no prior decision, so the row is created directly in its
    target state (`APPROVED` for a like, `DECLINED` for a pass/block). When a row
    already exists — a pending winger suggestion, or a prior decision being
    overwritten by a block — the lifecycle moves through `StateMachineService`
    rather than assigning the `state` column directly.

    Multiple wingers may have independently suggested the same recipient (each its
    own row, per the `unique_actor_recipient_suggestion` partial index), so this
    reads ALL matching rows, not just one — the dater's own swipe resolves every
    pending suggestion for that recipient at once, not just the first winger's.
    """
    existing = (
        (
            await db.execute(
                select(Decision).where(and_(Decision.actor_id == actor.id, Decision.recipient_id == recipient_id))
            )
        )
        .scalars()
        .all()
    )

    if not existing:
        db.add(Decision(actor_id=actor.id, recipient_id=recipient_id, state=target_state))
        await db.flush()
        return

    for row in existing:
        if row.state == target_state:
            continue
        if not decision_machine.can_transition(row, target_state, actor.role):
            continue
        await sm_service.transition(decision_machine, row, target_state, actor=actor)
    await db.flush()


async def insert_wing_suggestion(
    db: AsyncSession,
    dater_id: Sqid,
    recipient_id: Sqid,
    winger_id: Sqid,
    note: str | None,
    state: DecisionState,
) -> bool:
    """Winger creates a decision row on the dater's behalf, in its initial state.

    `state`:
      * PENDING  -> normal suggestion the dater can act on (with optional note).
      * DECLINED -> winger declines the recipient on the dater's behalf.

    Always a fresh row — on conflict it does nothing (this winger already suggested
    this recipient to this dater), so the winger never transitions an existing
    decision. Other wingers suggesting the same recipient land as separate rows
    (the `unique_actor_recipient_suggestion` partial index only collides on an
    identical (dater, recipient, winger) triple). A `WHERE NOT EXISTS` guard also
    blocks the insert when the dater already has a *real* (non-suggested) decision
    on this recipient — the normal pool flow already excludes decided candidates,
    but a stale cached pool page or a race with the dater's own swipe could still
    reach here. Returns True only on a genuinely new insert.
    """
    already_decided = exists(
        select(Decision.id).where(
            Decision.actor_id == dater_id,
            Decision.recipient_id == recipient_id,
            Decision.suggested_by.is_(None),
        )
    )
    stmt = (
        pg_insert(Decision)
        .from_select(
            ["actor_id", "recipient_id", "suggested_by", "state", "note"],
            select(
                literal(int(dater_id), type_=SqidType()),
                literal(int(recipient_id), type_=SqidType()),
                literal(int(winger_id), type_=SqidType()),
                literal(state),
                literal(note),
            ).where(~already_decided),
        )
        # Partial unique indexes can't back a named table CONSTRAINT (Postgres
        # constraints can't be partial), so the conflict target is inferred by
        # column list + the matching partial predicate instead of `constraint=`.
        .on_conflict_do_nothing(
            index_elements=["actor_id", "recipient_id", "suggested_by"],
            index_where=sa.text("suggested_by IS NOT NULL"),
        )
        .returning(Decision.id)
    )
    inserted = (await db.execute(stmt)).scalar_one_or_none()
    await db.flush()
    return inserted is not None


# ── Mutual-match lookup + match formation ─────────────────────────────────────


async def find_mutual_match(db: AsyncSession, user_a: Sqid, user_b: Sqid) -> Match | None:
    """Look up the matches row for a pair, regardless of who is user_a vs user_b.

    `matches` enforces user_a_id < user_b_id, so we order before querying.
    """
    lo, hi = (user_a, user_b) if user_a < user_b else (user_b, user_a)
    return (
        await db.execute(select(Match).where(and_(Match.user_a_id == lo, Match.user_b_id == hi)).limit(1))
    ).scalar_one_or_none()


async def both_sides_approved(db: AsyncSession, user_a: Sqid, user_b: Sqid) -> bool:
    """True when BOTH directions of the decision are 'approved' (mutual like).

    This is the condition checked before inserting a match row.
    """
    rows = (
        await db.execute(
            select(Decision.actor_id, Decision.recipient_id).where(
                and_(
                    Decision.state == DecisionState.APPROVED,
                    Decision.actor_id.in_([user_a, user_b]),
                    Decision.recipient_id.in_([user_a, user_b]),
                )
            )
        )
    ).all()
    pairs = {(a, r) for a, r in rows}
    return (user_a, user_b) in pairs and (user_b, user_a) in pairs


async def form_match_if_mutual(db: AsyncSession, user_a: Sqid, user_b: Sqid) -> Sqid | None:
    """Atomically form the pair's match iff both directions are 'approved'.

    A single guarded `INSERT ... SELECT`: the mutual-approved check and the row
    creation are one statement, so whichever like commits second sees both
    approvals and forms the row — closing the check-then-insert race. A genuine
    duplicate (both likes racing, or a re-like of an existing match) loses on the
    `unique_match` constraint and is swallowed by `ON CONFLICT DO NOTHING`.

    Returns the new match id only when THIS call formed it; `None` when the pair
    isn't (yet) mutual or a match already existed. The `matches_insert` RLS floor
    (`MutualMatchInsert`) independently re-checks the same condition, so even this
    guarded insert can't forge a non-mutual pairing.
    """
    lo, hi = (user_a, user_b) if user_a < user_b else (user_b, user_a)

    def _approved(actor: Sqid, recipient: Sqid) -> Any:
        return exists(
            select(Decision.id).where(
                Decision.actor_id == actor,
                Decision.recipient_id == recipient,
                Decision.state == DecisionState.APPROVED,
            )
        )

    # `SELECT :lo, :hi WHERE EXISTS(lo->hi approved) AND EXISTS(hi->lo approved)`
    # yields the one ordered pair row only when mutual, else zero rows.
    mutual_pair = select(
        literal(int(lo), type_=SqidType()),
        literal(int(hi), type_=SqidType()),
    ).where(_approved(lo, hi), _approved(hi, lo))

    stmt = (
        pg_insert(Match)
        .from_select(["user_a_id", "user_b_id"], mutual_pair)
        .on_conflict_do_nothing(constraint="unique_match")
        .returning(Match.id)
    )
    inserted = (await db.execute(stmt)).scalar_one_or_none()
    await db.flush()
    return inserted


# ── Authorization + push lookups ──────────────────────────────────────────────


async def push_tokens_for(db: AsyncSession, user_ids: list[Sqid]) -> list[str]:
    """Non-null Expo push tokens for the given users."""
    if not user_ids:
        return []
    rows = (await db.execute(select(Profile.push_token).where(Profile.id.in_(user_ids)))).all()
    return [token for (token,) in rows if token is not None]


async def dater_push_and_winger_name(
    db: AsyncSession, dater_id: Sqid, winger_id: Sqid
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


# ── Suggestions I made as a winger (the people-activity read) ──────────────────


async def fetch_my_suggestions(db: AsyncSession, winger_id: Sqid, limit: int) -> list[SuggestionRow]:
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
                Decision.state,
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
            state=state,
            has_match=bool(has_match),
            dater_id=dater_id,
            dater_name=dater_name,
            recipient_name=recipient_name,
            created_at=created_at,
        )
        for (
            decision_id,
            state,
            has_match,
            dater_id,
            dater_name,
            recipient_name,
            created_at,
        ) in rows
    ]
