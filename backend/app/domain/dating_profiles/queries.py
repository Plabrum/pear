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
    true,
)
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.elements import ColumnElement

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.enums import DatingStatus
from app.domain.dating_profiles.models import DatingProfile
from app.domain.dating_profiles.transformers import SwipeRow
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.matches.models import Match
from app.domain.photos.models import ProfilePhoto
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
            ProfilePhoto.approved_at.is_not(None),
        )
        .order_by(asc(ProfilePhoto.display_order))
        .limit(1)
        .correlate(DatingProfile)
        .scalar_subquery()
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
            ProfilePhoto.approved_at.is_not(None),
        )
        .correlate(DatingProfile)
        .scalar_subquery()
    )


# ── Shared preference filter ──────────────────────────────────────────────────


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

    Filters: active + `open` candidate, same city, the interested-gender match
    (empty array = "any"), age within `[ageFrom, ageTo]`, religion preference, and
    "candidate not already decided on".
    """
    age = age_expr()
    filters: list[ColumnElement[bool]] = [
        DatingProfile.is_active.is_(True),
        DatingProfile.dating_status == DatingStatus.OPEN,
        DatingProfile.city == viewer_dp.city,
        or_(
            func.cardinality(viewer_dp.interested_gender) == 0,
            Profile.gender == func.any(viewer_dp.interested_gender),
        ),
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
                Decision.decision.is_not(None),
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

    # The pending winger-suggestion for (viewer -> candidate): wing note, suggester
    # id, suggester chosen name — all three share the identical predicate, so a
    # single LEFT JOIN LATERAL surfaces them in one index probe (NULL columns when
    # there is no pending suggestion). The suggester `profiles` join is folded in.
    suggester = aliased(Profile, name="suggester")
    pending = (
        select(
            Decision.note.label("wing_note"),
            Decision.suggested_by.label("suggested_by"),
            suggester.chosen_name.label("suggester_name"),
        )
        .outerjoin(suggester, suggester.id == Decision.suggested_by)
        .where(
            Decision.actor_id == viewer_id,
            Decision.recipient_id == DatingProfile.user_id,
            Decision.decision.is_(None),
            Decision.suggested_by.is_not(None),
        )
        .limit(1)
        .lateral("pending_suggestion")
    )

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
                    Decision.decision.is_(None),
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
                    Decision.decision.is_(None),
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
                    Decision.decision == DecisionType.APPROVED,
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
            DatingProfile.dating_status.label("dating_status"),
            DatingProfile.interests.label("interests"),
            photos.label("photos"),
            pending.c.wing_note.label("wing_note"),
            pending.c.suggested_by.label("suggested_by"),
            pending.c.suggester_name.label("suggester_name"),
        )
        .select_from(DatingProfile)
        .join(Profile, Profile.id == DatingProfile.user_id)
        .join(vdp, vdp.user_id == viewer_id)
        .outerjoin(pending, true())
        .where(*filters)
        .order_by(desc(pending.c.suggested_by.is_not(None)), desc(DatingProfile.created_at))
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
            DatingProfile.dating_status.label("dating_status"),
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
        wing_note=r.get("wing_note"),
        suggested_by=r.get("suggested_by"),
        suggester_name=r.get("suggester_name"),
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
        lk.decision == DecisionType.APPROVED,
        DatingProfile.is_active.is_(True),
        DatingProfile.dating_status == DatingStatus.OPEN,
        DatingProfile.city == vdp.city,
        or_(
            func.cardinality(vdp.interested_gender) == 0,
            Profile.gender == func.any(vdp.interested_gender),
        ),
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
                Decision.decision.is_not(None),
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
    """True when there is an ACTIVE contact (dater -> winger)."""
    stmt = (
        select(literal_column("1"))
        .select_from(Contact)
        .where(
            Contact.user_id == dater_id,
            Contact.winger_id == winger_id,
            Contact.wingperson_status == WingpersonStatus.ACTIVE,
        )
        .limit(1)
    )
    return (await db.execute(stmt)).first() is not None
