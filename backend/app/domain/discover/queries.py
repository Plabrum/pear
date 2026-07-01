"""SQLAlchemy reads for the FEED cluster (discover / wing-pool / likes-you).

Ported from the three Hono query files:
  * supabase/functions/api/domains/discover/queries.ts   (fetchDiscoverPool)
  * supabase/functions/api/domains/wing-pool/queries.ts   (fetchWingPool, isActiveWingperson)
  * supabase/functions/api/domains/likes-you/queries.ts   (fetchLikesYouPool, fetchLikesYouCount)

The three feeds share one *preference filter*: the viewer's (or dater's) own
`dating_profiles` row scopes candidates by city, interested-gender, age range and
religious preference, and excludes candidates the viewer has already decided on.
`build_preference_filters` is the single source of that SQL so the feeds can never
diverge; `wing_pool` and `likes_you` import it from here.

RLS enforces *access*; these filters are *relevance* (the recipe's explicit
distinction). First arg is always `db: AsyncSession`, no Litestar/msgspec imports.

Enum-storage note: the Phase-3 models store enum members as their `.name` in TEXT
columns (and TEXT[] arrays), not as Postgres native enums. So `profiles.gender`
holds e.g. `'MALE'` and `dating_profiles.interested_gender` holds `'{MALE,FEMALE}'`;
both sides use the same `.name` encoding, so the Hono `gender = any(interested)` /
`interested = '{}'` comparisons port directly. `func.any(...)` over the gender
array compares against `Profile.gender`, whose `TextEnum` bind/result handling
keeps both sides on the `.name` form.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

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

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact
from app.domain.dating_profiles.enums import DatingStatus
from app.domain.dating_profiles.models import DatingProfile
from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.discover.transformers import DiscoverRow
from app.domain.likes_you.transformers import LikesYouRow
from app.domain.matches.models import Match
from app.domain.photos.models import ProfilePhoto
from app.domain.profiles.models import Profile
from app.domain.wing_pool.transformers import WingPoolRow

# ── Shared scalar expressions ─────────────────────────────────────────────────


def age_expr() -> ColumnElement[int]:
    """`extract(year from age(date_of_birth))::int` — a candidate's integer age.

    Ports the Hono `ageExpr`; `age(timestamp)` returns an interval whose whole
    `year` part is the years-of-age value.
    """
    return sa_cast(func.extract("year", func.age(Profile.date_of_birth)), Integer)


def first_photo_expr() -> ColumnElement[Any]:
    """Correlated subquery: the candidate's first approved photo URL (or NULL).

    Ports the wing-pool / likes-you `firstPhotoExpr`: lowest display_order among
    the candidate's approved photos.
    """
    return (
        select(ProfilePhoto.storage_url)
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
    """Correlated subquery: all approved photo URLs ordered by display_order.

    Ports the discover `photosExpr` (`coalesce(array_agg(... order by ...), '{}')`).
    """
    return (
        select(
            func.coalesce(
                func.array_agg(aggregate_order_by(ProfilePhoto.storage_url, ProfilePhoto.display_order)),
                literal_column("'{}'"),
            )
        )
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
    decided_actor_id: UUID,
) -> list[ColumnElement[bool]]:
    """The shared candidate preference/relevance filters.

    `viewer_dp` is the *aliased* `dating_profiles` row owning the preferences (the
    viewer's profile for discover/likes-you, the dater's profile for wing-pool) —
    typed `Any` because `aliased(...)` yields an `AliasedClass` whose attribute
    access SQLAlchemy resolves at runtime, not statically.
    `decided_actor_id` is the actor whose prior non-null decisions exclude a
    candidate (the viewer for discover/likes-you, the dater for wing-pool).

    Mirrors the Hono filter list exactly: active + `open` candidate, same city, the
    interested-gender match (empty array = "any"), age within `[ageFrom, ageTo]`,
    religion preference, and "candidate not already decided on".
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


# ── discover ──────────────────────────────────────────────────────────────────


async def fetch_discover_pool(
    db: AsyncSession,
    *,
    viewer_id: UUID,
    page_size: int,
    page_offset: int,
    filter_winger_id: UUID | None = None,
    winger_only: bool = False,
    likes_you_only: bool = False,
) -> list[DiscoverRow]:
    """Port of Hono `fetchDiscoverPool`.

    The dater swipe feed: candidates matching the viewer's preferences, with the
    pending-suggestion wing note + suggester surfaced, and the optional
    filterWingerId / wingerOnly / likesYouOnly EXISTS branches. Ordered
    suggestions-first then newest, paginated.
    """
    vdp = aliased(DatingProfile, name="vdp")

    age = age_expr()
    photos = photos_array_expr()

    # The pending winger-suggestion for (viewer -> candidate): wing note, suggester
    # id, suggester chosen name. Each is an independent correlated scalar subquery
    # (NULL when there is no pending suggestion), mirroring the Hono SQL.
    wing_note_sq = (
        select(Decision.note)
        .where(
            Decision.actor_id == viewer_id,
            Decision.recipient_id == DatingProfile.user_id,
            Decision.decision.is_(None),
            Decision.suggested_by.is_not(None),
        )
        .limit(1)
        .correlate(DatingProfile)
        .scalar_subquery()
    )
    suggested_by_sq = (
        select(Decision.suggested_by)
        .where(
            Decision.actor_id == viewer_id,
            Decision.recipient_id == DatingProfile.user_id,
            Decision.decision.is_(None),
            Decision.suggested_by.is_not(None),
        )
        .limit(1)
        .correlate(DatingProfile)
        .scalar_subquery()
    )
    suggester_name_sq = (
        select(Profile.chosen_name)
        .select_from(Decision)
        .join(Profile, Profile.id == Decision.suggested_by)
        .where(
            Decision.actor_id == viewer_id,
            Decision.recipient_id == DatingProfile.user_id,
            Decision.decision.is_(None),
            Decision.suggested_by.is_not(None),
        )
        .limit(1)
        .correlate(DatingProfile)
        .scalar_subquery()
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
            wing_note_sq.label("wing_note"),
            suggested_by_sq.label("suggested_by"),
            suggester_name_sq.label("suggester_name"),
        )
        .select_from(DatingProfile)
        .join(Profile, Profile.id == DatingProfile.user_id)
        .join(vdp, vdp.user_id == viewer_id)
        .where(*filters)
        .order_by(desc(suggested_by_sq.is_not(None)), desc(DatingProfile.created_at))
        .limit(page_size)
        .offset(page_offset)
    )

    rows = (await db.execute(stmt)).mappings().all()
    return [
        DiscoverRow(
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
            wing_note=r["wing_note"],
            suggested_by=r["suggested_by"],
            suggester_name=r["suggester_name"],
        )
        for r in rows
    ]


# ── wing-pool ─────────────────────────────────────────────────────────────────


async def is_active_wingperson(db: AsyncSession, winger_id: UUID, dater_id: UUID) -> bool:
    """Port of Hono `isActiveWingperson`: an ACTIVE contact (dater -> winger)."""
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


async def fetch_wing_pool(
    db: AsyncSession,
    *,
    winger_id: UUID,
    dater_id: UUID,
    page_size: int,
    page_offset: int,
) -> list[WingPoolRow]:
    """Port of Hono `fetchWingPool`.

    The dater-scoped candidate pool a winger can suggest: candidates matching the
    DATER's preferences, excluding the dater and the winger, excluding candidates
    the dater already decided on. Ordered newest, paginated.
    """
    ddp = aliased(DatingProfile, name="ddp")
    age = age_expr()
    first_photo = first_photo_expr()

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
            first_photo.label("first_photo"),
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
    return [
        WingPoolRow(
            profile_id=r["profile_id"],
            user_id=r["user_id"],
            chosen_name=r["chosen_name"],
            gender=r["gender"],
            age=r["age"],
            city=r["city"],
            bio=r["bio"],
            dating_status=r["dating_status"],
            interests=list(r["interests"]),
            first_photo=r["first_photo"],
        )
        for r in rows
    ]


# ── likes-you ─────────────────────────────────────────────────────────────────


def _build_likes_you_filters(
    viewer_id: UUID,
    *,
    lk: Any,
    vdp: Any,
    age: ColumnElement[int],
) -> list[ColumnElement[bool]]:
    """Port of Hono `buildLikesYouFilters` over aliases `lk` (the like) + `vdp`.

    `lk.recipient_id = viewer` AND `lk.decision = approved`, the viewer's
    preference filters against the candidate, "not yet decided by viewer", and "no
    existing match". Shared verbatim between the pool and the count. `lk` / `vdp`
    are aliased classes (typed `Any`; resolved at runtime by SQLAlchemy).
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


async def fetch_likes_you_pool(
    db: AsyncSession,
    *,
    viewer_id: UUID,
    page_size: int,
    page_offset: int,
) -> list[LikesYouRow]:
    """Port of Hono `fetchLikesYouPool`.

    Profiles whose `approved` decision targets the viewer, still available (same
    preference filters, not yet matched, not yet decided-by-viewer), with the
    optional pending winger-suggestion (note + suggester) left-joined. Ordered by
    most-recent like, paginated.
    """
    lk = aliased(Decision, name="lk")
    vdp = aliased(DatingProfile, name="vdp")
    pending_sug = aliased(Decision, name="pending_sug")
    suggester = aliased(Profile, name="s")
    age = age_expr()
    first_photo = first_photo_expr()

    filters = _build_likes_you_filters(viewer_id, lk=lk, vdp=vdp, age=age)

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
            first_photo.label("first_photo"),
            pending_sug.note.label("wing_note"),
            pending_sug.suggested_by.label("suggested_by"),
            suggester.chosen_name.label("suggester_name"),
        )
        .select_from(lk)
        .join(Profile, Profile.id == lk.actor_id)
        .join(DatingProfile, DatingProfile.user_id == lk.actor_id)
        .join(vdp, vdp.user_id == viewer_id)
        .outerjoin(
            pending_sug,
            (pending_sug.actor_id == viewer_id)
            & (pending_sug.recipient_id == lk.actor_id)
            & (pending_sug.decision.is_(None))
            & (pending_sug.suggested_by.is_not(None)),
        )
        .outerjoin(suggester, suggester.id == pending_sug.suggested_by)
        .where(*filters)
        .order_by(desc(lk.created_at))
        .limit(page_size)
        .offset(page_offset)
    )

    rows = (await db.execute(stmt)).mappings().all()
    return [
        LikesYouRow(
            profile_id=r["profile_id"],
            user_id=r["user_id"],
            chosen_name=r["chosen_name"],
            gender=r["gender"],
            age=r["age"],
            city=r["city"],
            bio=r["bio"],
            dating_status=r["dating_status"],
            interests=list(r["interests"]),
            first_photo=r["first_photo"],
            wing_note=r["wing_note"],
            suggested_by=r["suggested_by"],
            suggester_name=r["suggester_name"],
        )
        for r in rows
    ]


async def fetch_likes_you_count(db: AsyncSession, viewer_id: UUID) -> int:
    """Port of Hono `fetchLikesYouCount`: count of the same likes-you pool."""
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
