from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Integer,
    asc,
    cast as sa_cast,
    desc,
    exists,
    func,
    literal_column,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.domain.contacts.queries import is_active_wingperson as contacts_is_active_wingperson
from app.domain.dating_profiles.enums import DatingStatus
from app.domain.dating_profiles.models import DatingProfile
from app.domain.dating_profiles.transformers import SwipeRow, WingSuggestionRow
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.photos.enums import PhotoApprovalState
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.enums import UserRole
from app.domain.profiles.models import Profile
from app.platform.media.queries import servable_key_expr
from app.utils.sqids import Sqid

# ── Shared scalar expressions ─────────────────────────────────────────────────


def age_expr() -> ColumnElement[int]:
    """`extract(year from age(date_of_birth))::int` — a candidate's integer age.

    `age(timestamp)` returns an interval whose whole `year` part is the
    years-of-age value.
    """
    return sa_cast(func.extract("year", func.age(Profile.date_of_birth)), Integer)


def first_photo_expr() -> ColumnElement[Any]:
    """Correlated subquery: the candidate's first approved photo URL (or NULL).

    Lowest display_order among the candidate's approved photos.
    """
    return (
        select(servable_key_expr(ProfilePhoto.media_id))
        .where(
            ProfilePhoto.dating_profile_id == DatingProfile.id,
            ProfilePhoto.state == PhotoApprovalState.APPROVED,
        )
        .order_by(asc(ProfilePhoto.display_order))
        .limit(1)
        .correlate(DatingProfile)
        .scalar_subquery()
    )


def wing_suggestions_expr(viewer_id: Sqid) -> ColumnElement[Any]:
    """Correlated subquery: every PENDING winger suggestion of the candidate for
    `viewer_id`, oldest first — `json_agg(json_build_object(...) ORDER BY created_at)`.

    Multiple wingers may each independently suggest the same candidate (the
    `unique_actor_recipient_suggestion` partial index allows one row per
    (dater, recipient, winger)), so this returns the full list rather than the
    single most-recent pick the old LATERAL-joined LIMIT 1 subquery surfaced.
    """
    suggester = aliased(Profile, name="suggester")
    ordered = aggregate_order_by(
        func.json_build_object(
            "wingerId",
            Decision.suggested_by,
            "wingerName",
            suggester.chosen_name,
            "note",
            Decision.note,
        ),
        Decision.created_at,
    )
    return (
        select(func.coalesce(func.json_agg(ordered), literal_column("'[]'::json")))
        .select_from(Decision)
        .outerjoin(suggester, suggester.id == Decision.suggested_by)
        .where(
            Decision.actor_id == viewer_id,
            Decision.recipient_id == DatingProfile.user_id,
            Decision.state == DecisionState.PENDING,
            Decision.suggested_by.is_not(None),
        )
        .correlate(DatingProfile)
        .scalar_subquery()
    )


def has_pending_suggestion_expr(viewer_id: Sqid) -> ColumnElement[bool]:
    """EXISTS a PENDING winger suggestion of the candidate for `viewer_id` — used to
    order suggestions-first without materializing the full `wing_suggestions_expr`
    payload just for ordering.
    """
    return exists(
        select(literal_column("1"))
        .select_from(Decision)
        .where(
            Decision.actor_id == viewer_id,
            Decision.recipient_id == DatingProfile.user_id,
            Decision.state == DecisionState.PENDING,
            Decision.suggested_by.is_not(None),
        )
    )


def photos_array_expr() -> ColumnElement[Any]:
    """Correlated subquery: all approved photo URLs ordered by display_order
    (`coalesce(array_agg(... order by ...), '{}')`).
    """
    ordered_keys = aggregate_order_by(servable_key_expr(ProfilePhoto.media_id), ProfilePhoto.display_order)
    return (
        select(func.coalesce(func.array_agg(ordered_keys), literal_column("'{}'")))
        .where(
            ProfilePhoto.dating_profile_id == DatingProfile.id,
            ProfilePhoto.state == PhotoApprovalState.APPROVED,
        )
        .correlate(DatingProfile)
        .scalar_subquery()
    )


# ── Shared preference filter ──────────────────────────────────────────────────


def candidate_wants_viewer_gender(viewer_user_id: Sqid) -> ColumnElement[bool]:
    """Reciprocal gender filter: the candidate's own `interested_gender` must include
    the viewer's gender (empty array = "any").

    Pairs with the forward "viewer wants candidate's gender" check so matching is
    **bidirectional** — a candidate only surfaces when each side is open to the other's
    gender. `DatingProfile` is the candidate row (the main query entity); the viewer's
    gender is read via a non-correlated scalar subquery on an aliased `profiles`.
    """
    vp = aliased(Profile)
    viewer_gender = select(vp.gender).where(vp.id == viewer_user_id).scalar_subquery()
    return or_(
        func.cardinality(DatingProfile.interested_gender) == 0,
        viewer_gender == func.any(DatingProfile.interested_gender),
    )


def build_preference_filters(
    viewer_dp: Any,
    *,
    decided_actor_id: Sqid,
) -> list[ColumnElement[bool]]:
    """The shared candidate preference/relevance filters.

    `viewer_dp` is the *aliased* `dating_profiles` row owning the preferences (the
    viewer's profile in the dater context, the dater's profile in the winger
    context) — typed `Any` because `aliased(...)` yields an `AliasedClass` whose
    attribute access SQLAlchemy resolves at runtime, not statically.
    `decided_actor_id` is the actor whose prior non-null decisions exclude a
    candidate (the viewer in the dater context, the dater in the winger context).

    Filters: active + `open` candidate, same city, the **bidirectional** interested-
    gender match (each side open to the other's gender; empty array = "any"), age
    within `[ageFrom, ageTo]`, religion preference, and "candidate not already
    decided on". `decided_actor_id` doubles as the viewer's user id — it owns
    `viewer_dp` in both the dater and winger contexts.
    """
    age = age_expr()
    filters: list[ColumnElement[bool]] = [
        DatingProfile.is_active.is_(True),
        DatingProfile.state == DatingStatus.OPEN,
        # A candidate who is currently winging (role == WINGER) is out of the pool —
        # "winging" now lives on the profile role, not a `dating_status` value.
        Profile.state != UserRole.WINGER,
        DatingProfile.city == viewer_dp.city,
        # Forward: viewer is open to the candidate's gender.
        or_(
            func.cardinality(viewer_dp.interested_gender) == 0,
            Profile.gender == func.any(viewer_dp.interested_gender),
        ),
        # Reverse: candidate is open to the viewer's gender.
        candidate_wants_viewer_gender(decided_actor_id),
        age >= viewer_dp.age_from,
        or_(viewer_dp.age_to.is_(None), age <= viewer_dp.age_to),
        or_(
            viewer_dp.religious_preference.is_(None),
            DatingProfile.religion == viewer_dp.religious_preference,
        ),
        ~exists(
            select(literal_column("1"))
            .select_from(Decision)
            .where(
                Decision.actor_id == decided_actor_id,
                Decision.recipient_id == DatingProfile.user_id,
                Decision.state != DecisionState.PENDING,
            )
        ),
    ]
    return filters


# ── The collapsed swipe read ──────────────────────────────────────────────────


async def fetch_swipe_pool(
    db: AsyncSession,
    *,
    viewer_id: Sqid,
    page_size: int,
    page_offset: int,
    likes_you_only: bool = False,
    winger_only: bool = False,
    filter_winger_id: Sqid | None = None,
    filter_dater_id: Sqid | None = None,
) -> list[SwipeRow]:
    """The single parametrized swipe read on `DatingProfile`.

    Replaces the former discover / likes-you / wing-pool feeds with one query +
    filters:

      * default (no context flags): the dater swipe feed for `viewer_id` — the
        candidate pool matching the viewer's preferences, suggestions-first.
      * `likes_you_only`: restrict to candidates whose `approved` decision targets
        the viewer and who aren't already matched.
      * `winger_only`: restrict to candidates with a pending winger suggestion for
        the viewer; `filter_winger_id` narrows to a single suggesting winger.
      * `filter_dater_id`: the winger context — scope to the DATER's preferences
        (gated to an active wingperson by the caller), excluding the dater and the
        viewing winger. Mutually exclusive with the dater-context flags.

    Each row carries the pending-suggestion wing note + suggester surfaced via
    correlated subqueries, the candidate's identity (joined Profile), and the
    approved-photo array. Ordered suggestions-first then newest, paginated.
    """
    if filter_dater_id is not None:
        return await _fetch_winger_context(
            db,
            winger_id=viewer_id,
            dater_id=filter_dater_id,
            page_size=page_size,
            page_offset=page_offset,
        )
    return await _fetch_dater_context(
        db,
        viewer_id=viewer_id,
        page_size=page_size,
        page_offset=page_offset,
        likes_you_only=likes_you_only,
        winger_only=winger_only,
        filter_winger_id=filter_winger_id,
    )


async def _fetch_dater_context(
    db: AsyncSession,
    *,
    viewer_id: Sqid,
    page_size: int,
    page_offset: int,
    likes_you_only: bool,
    winger_only: bool,
    filter_winger_id: Sqid | None,
) -> list[SwipeRow]:
    """The dater-facing swipe pool (discover / likes-you / winger-only)."""
    vdp = aliased(DatingProfile, name="vdp")

    age = age_expr()
    photos = photos_array_expr()
    suggestions = wing_suggestions_expr(viewer_id)
    has_suggestion = has_pending_suggestion_expr(viewer_id)

    filters = build_preference_filters(vdp, decided_actor_id=viewer_id)
    # exclude self (the viewer is the dater here)
    filters.append(DatingProfile.user_id != viewer_id)

    if filter_winger_id is not None:
        filters.append(
            exists(
                select(literal_column("1"))
                .select_from(Decision)
                .where(
                    Decision.actor_id == viewer_id,
                    Decision.recipient_id == DatingProfile.user_id,
                    Decision.suggested_by == filter_winger_id,
                    Decision.state == DecisionState.PENDING,
                )
            )
        )

    if winger_only:
        filters.append(
            exists(
                select(literal_column("1"))
                .select_from(Decision)
                .where(
                    Decision.actor_id == viewer_id,
                    Decision.recipient_id == DatingProfile.user_id,
                    Decision.state == DecisionState.PENDING,
                    Decision.suggested_by.is_not(None),
                )
            )
        )

    if likes_you_only:
        filters.append(
            exists(
                select(literal_column("1"))
                .select_from(Decision)
                .where(
                    Decision.actor_id == DatingProfile.user_id,
                    Decision.recipient_id == viewer_id,
                    Decision.state == DecisionState.APPROVED,
                )
            )
        )
        filters.append(
            ~exists(
                select(literal_column("1"))
                .select_from(Match)
                .where(
                    or_(
                        (Match.user_a_id == viewer_id) & (Match.user_b_id == DatingProfile.user_id),
                        (Match.user_a_id == DatingProfile.user_id) & (Match.user_b_id == viewer_id),
                    )
                )
            )
        )

    stmt = (
        select(
            DatingProfile.id.label("profile_id"),
            DatingProfile.user_id.label("user_id"),
            Profile.chosen_name.label("chosen_name"),
            Profile.gender.label("gender"),
            age.label("age"),
            DatingProfile.city.label("city"),
            DatingProfile.bio.label("bio"),
            DatingProfile.state.label("dating_status"),
            DatingProfile.interests.label("interests"),
            photos.label("photos"),
            suggestions.label("suggestions"),
        )
        .select_from(DatingProfile)
        .join(Profile, Profile.id == DatingProfile.user_id)
        .join(vdp, vdp.user_id == viewer_id)
        .where(*filters)
        .order_by(desc(has_suggestion), desc(DatingProfile.created_at))
        .limit(page_size)
        .offset(page_offset)
    )

    rows = (await db.execute(stmt)).mappings().all()
    return [_row_to_swipe(r) for r in rows]


async def _fetch_winger_context(
    db: AsyncSession,
    *,
    winger_id: Sqid,
    dater_id: Sqid,
    page_size: int,
    page_offset: int,
) -> list[SwipeRow]:
    """The dater-scoped candidate pool a winger can suggest from.

    Candidates matching the DATER's preferences, excluding the dater and the
    winger, excluding candidates the dater already decided on. Ordered newest,
    paginated. No pending-suggestion surfacing in this context.
    """
    ddp = aliased(DatingProfile, name="ddp")
    age = age_expr()
    photos = photos_array_expr()

    filters = build_preference_filters(ddp, decided_actor_id=dater_id)
    filters.append(DatingProfile.user_id != dater_id)
    filters.append(DatingProfile.user_id != winger_id)

    stmt = (
        select(
            DatingProfile.id.label("profile_id"),
            DatingProfile.user_id.label("user_id"),
            Profile.chosen_name.label("chosen_name"),
            Profile.gender.label("gender"),
            age.label("age"),
            DatingProfile.city.label("city"),
            DatingProfile.bio.label("bio"),
            DatingProfile.state.label("dating_status"),
            DatingProfile.interests.label("interests"),
            photos.label("photos"),
        )
        .select_from(DatingProfile)
        .join(Profile, Profile.id == DatingProfile.user_id)
        .join(ddp, ddp.user_id == dater_id)
        .where(*filters)
        .order_by(desc(DatingProfile.created_at))
        .limit(page_size)
        .offset(page_offset)
    )

    rows = (await db.execute(stmt)).mappings().all()
    return [_row_to_swipe(r) for r in rows]


def _row_to_swipe(r: Any) -> SwipeRow:
    return SwipeRow(
        profile_id=r["profile_id"],
        user_id=r["user_id"],
        chosen_name=r["chosen_name"],
        gender=r["gender"],
        age=r["age"],
        city=r["city"],
        bio=r["bio"],
        dating_status=r["dating_status"],
        interests=list(r["interests"]),
        photos=list(r["photos"] or []),
        # The winger context omits the `suggestions` column entirely (no pending-
        # suggestion surfacing there), so this is [] rather than a raw JSON payload.
        suggestions=[
            WingSuggestionRow(winger_id=Sqid(s["wingerId"]), winger_name=s["wingerName"], note=s["note"])
            for s in (r.get("suggestions") or [])
        ],
    )


# ── likes-you count ───────────────────────────────────────────────────────────


def _build_likes_you_filters(
    viewer_id: Sqid,
    *,
    lk: Any,
    vdp: Any,
    age: ColumnElement[int],
) -> list[ColumnElement[bool]]:
    """Build the likes-you filters over aliases `lk` (the like) + `vdp`.

    `lk.recipient_id = viewer` AND `lk.decision = approved`, the viewer's
    preference filters against the candidate, "not yet decided by viewer", and "no
    existing match". `lk` / `vdp` are aliased classes (typed `Any`; resolved at
    runtime by SQLAlchemy).
    """
    filters: list[ColumnElement[bool]] = [
        lk.recipient_id == viewer_id,
        lk.state == DecisionState.APPROVED,
        DatingProfile.is_active.is_(True),
        DatingProfile.state == DatingStatus.OPEN,
        # A winging candidate (role == WINGER) is excluded from the likes-you pool too.
        Profile.state != UserRole.WINGER,
        DatingProfile.city == vdp.city,
        # Forward: viewer is open to the liker's gender.
        or_(
            func.cardinality(vdp.interested_gender) == 0,
            Profile.gender == func.any(vdp.interested_gender),
        ),
        # Reverse: liker is open to the viewer's gender.
        candidate_wants_viewer_gender(viewer_id),
        age >= vdp.age_from,
        or_(vdp.age_to.is_(None), age <= vdp.age_to),
        or_(
            vdp.religious_preference.is_(None),
            DatingProfile.religion == vdp.religious_preference,
        ),
        ~exists(
            select(literal_column("1"))
            .select_from(Decision)
            .where(
                Decision.actor_id == viewer_id,
                Decision.recipient_id == lk.actor_id,
                Decision.state != DecisionState.PENDING,
            )
        ),
        ~exists(
            select(literal_column("1"))
            .select_from(Match)
            .where(
                or_(
                    (Match.user_a_id == viewer_id) & (Match.user_b_id == lk.actor_id),
                    (Match.user_a_id == lk.actor_id) & (Match.user_b_id == viewer_id),
                )
            )
        ),
    ]
    return filters


async def fetch_likes_you_count(db: AsyncSession, viewer_id: Sqid) -> int:
    """Count of the same likes-you pool surfaced by `fetch_swipe_pool(likesYouOnly)`."""
    lk = aliased(Decision, name="lk")
    vdp = aliased(DatingProfile, name="vdp")
    age = age_expr()

    filters = _build_likes_you_filters(viewer_id, lk=lk, vdp=vdp, age=age)

    core = (
        select(literal_column("1"))
        .select_from(lk)
        .join(Profile, Profile.id == lk.actor_id)
        .join(DatingProfile, DatingProfile.user_id == lk.actor_id)
        .join(vdp, vdp.user_id == viewer_id)
        .where(*filters)
    )
    count_stmt = select(func.count()).select_from(core.subquery())
    return (await db.execute(count_stmt)).scalar_one()


# ── Authorization lookup (winger context gate) ────────────────────────────────


async def is_active_wingperson(db: AsyncSession, winger_id: Sqid, dater_id: Sqid) -> bool:
    """True when there is an ACTIVE contact (dater -> winger).

    The winger-context gate keeps its `(winger_id, dater_id)` argument order for its
    callers; the active-contact predicate itself is the shared
    `contacts.queries.is_active_wingperson` (one SQL definition).
    """
    return await contacts_is_active_wingperson(db, dater_id, winger_id)
