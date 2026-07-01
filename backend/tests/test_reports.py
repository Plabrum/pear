from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.dating_profiles.actions import Report
from app.domain.dating_profiles.schemas import ReportActionData
from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision
from app.domain.reports.models import ProfileReport
from app.platform.actions.deps import ActionDeps
from app.platform.auth.principal import User
from app.platform.state_machine.machine import StateMachineService
from app.platform.state_machine.roles import Role
from tests.fixtures.graph import ActingAs, DomainGraph

# `asyncio_mode = "auto"` (pyproject.toml) runs `async def test_*` without a marker.


def _deps(session: AsyncSession, *, user_id, role: Role = Role.DATER) -> ActionDeps:
    """ActionDeps backed by the test session and a given actor."""
    push = MagicMock()
    push.send = AsyncMock()
    return ActionDeps(
        transaction=session,
        user=User(id=user_id, role=role),
        request=MagicMock(),
        config=MagicMock(),
        push=push,
        email=MagicMock(),
        state_machine_service=StateMachineService(transaction=session),
    )


# ── report via the new DatingProfile action: happy path ──────────────────────


async def test_report_inserts_report_and_declines(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a reports dater_c's profile (no prior decision between them).
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = ReportActionData(reason="Inappropriate photos")

    result = await Report.execute(graph.dating_profile_c, data, db_session, deps.user, deps)
    assert result.message == "Report filed"
    assert "/decisions" in result.invalidate_queries

    # The report row was recorded.
    report = (
        await db_session.execute(
            select(ProfileReport).where(
                ProfileReport.reporter_id == graph.dater_a.id,
                ProfileReport.reported_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert report.reason == "Inappropriate photos"

    # A declined decision was upserted so the reported profile leaves the queue.
    decision = (
        await db_session.execute(
            select(Decision).where(
                Decision.actor_id == graph.dater_a.id,
                Decision.recipient_id == graph.dater_c.id,
            )
        )
    ).scalar_one()
    assert decision.state == DecisionState.DECLINED


async def test_report_overwrites_existing_decision_to_declined(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a previously liked dater_c; reporting them overwrites the like to a pass
    # (upsert on the unique (actor, recipient) pair).
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            state=DecisionState.APPROVED,
        )
    )
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = ReportActionData(reason="Changed my mind — abusive")
    await Report.execute(graph.dating_profile_c, data, db_session, deps.user, deps)

    # Still exactly one decision row for the pair, now declined (upsert, not insert).
    rows = (
        (
            await db_session.execute(
                select(Decision).where(
                    Decision.actor_id == graph.dater_a.id,
                    Decision.recipient_id == graph.dater_c.id,
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert rows[0].state == DecisionState.DECLINED


# ── reports RLS: own-report scoping ──────────────────────────────────────────


async def test_report_under_rls_actor(graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs) -> None:
    """End-to-end under a real RLS actor (not system mode): the reporter can insert
    their own report and read it back; another user cannot see it.

    This exercises the `profile_reports_select` policy (the insert is rejected
    without a SELECT policy under FORCE RLS), plus the INSERT WITH CHECK scoping.
    """
    async with acting_as(graph.dater_a.id) as s:
        deps = _deps(s, user_id=graph.dater_a.id)
        data = ReportActionData(reason="RLS path")
        await Report.execute(graph.dating_profile_c, data, s, deps.user, deps)

        # The reporter reads back their own report (SELECT policy permits it).
        mine = (
            (await s.execute(select(ProfileReport).where(ProfileReport.reporter_id == graph.dater_a.id)))
            .scalars()
            .all()
        )
        assert len(mine) == 1
        assert mine[0].reported_id == graph.dater_c.id

    # A different user cannot see dater_a's report (own-report SELECT scoping).
    async with acting_as(graph.dater_b.id) as s:
        visible = (
            (await s.execute(select(ProfileReport).where(ProfileReport.reporter_id == graph.dater_a.id)))
            .scalars()
            .all()
        )
        assert visible == []


# ── report action: self gate denial ──────────────────────────────────────────


async def test_report_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    # is_available blocks reporting your own profile (the framework raises 403).
    deps = _deps(db_session, user_id=graph.dater_a.id)
    assert Report.is_available(graph.dating_profile_a, deps.user, deps) is False

    # No report exists for the self pair.
    report = (
        await db_session.execute(select(ProfileReport).where(ProfileReport.reporter_id == graph.dater_a.id))
    ).scalar_one_or_none()
    assert report is None
