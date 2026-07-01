"""Tests for the ported `reports` domain.

The Hono `reports` domain shipped no `*.test.ts`; it is write-only (a single
`POST /reports`). These pytest cases preserve the contract the port must keep:

  reports action (write):
    * FileReport — inserts a `profile_reports` row AND upserts a
      `decision = 'declined'` for (reporter, recipient) so the reported profile
      leaves the reporter's queue (matching the Hono handler's two effects).
    * Upsert overwrite — a pre-existing like is overwritten to a pass when the
      reporter files a report against that recipient.
    * Self-report gate denial — reporting yourself raises 400.

Seeding/reads run under the system-mode `db_session` (RLS is covered separately by
tests/test_rls.py). The action is driven directly with a hand-built `ActionDeps`,
mirroring tests/test_profiles.py / tests/test_decisions.py.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.decisions.enums import DecisionType
from app.domain.decisions.models import Decision
from app.domain.reports.actions import FileReport
from app.domain.reports.exceptions import CannotReportSelfError
from app.domain.reports.models import ProfileReport
from app.domain.reports.schemas import CreateReportData
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


# ── reports action: happy path ───────────────────────────────────────────────


async def test_file_report_inserts_report_and_declines(graph: DomainGraph, db_session: AsyncSession) -> None:
    # dater_a reports dater_c (no prior decision between them).
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreateReportData(recipientId=graph.dater_c.id, reason="Inappropriate photos")

    result = await FileReport.execute(data, db_session, deps)
    assert result.message == "Report filed"
    assert "decisions" in result.invalidate_queries

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
    assert decision.decision == DecisionType.DECLINED


async def test_file_report_overwrites_existing_decision_to_declined(
    graph: DomainGraph, db_session: AsyncSession
) -> None:
    # dater_a previously liked dater_c; reporting them overwrites the like to a pass
    # (mirrors Hono's onConflictDoUpdate on the unique (actor, recipient) pair).
    db_session.add(
        Decision(
            actor_id=graph.dater_a.id,
            recipient_id=graph.dater_c.id,
            decision=DecisionType.APPROVED,
        )
    )
    await db_session.flush()

    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreateReportData(recipientId=graph.dater_c.id, reason="Changed my mind — abusive")
    await FileReport.execute(data, db_session, deps)

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
    assert rows[0].decision == DecisionType.DECLINED


# ── reports RLS: own-report scoping ──────────────────────────────────────────


async def test_file_report_under_rls_actor(graph: DomainGraph, db_session: AsyncSession, acting_as: ActingAs) -> None:
    """End-to-end under a real RLS actor (not system mode): the reporter can insert
    their own report and read it back; another user cannot see it.

    This exercises the Phase-5 `profile_reports_select` policy added for the ORM's
    `INSERT ... RETURNING` (the insert is rejected without a SELECT policy under
    FORCE RLS), plus the existing INSERT WITH CHECK scoping.
    """
    async with acting_as(graph.dater_a.id) as s:
        deps = _deps(s, user_id=graph.dater_a.id)
        data = CreateReportData(recipientId=graph.dater_c.id, reason="RLS path")
        await FileReport.execute(data, s, deps)

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


# ── reports action: gate denial ──────────────────────────────────────────────


async def test_file_report_self_denied(graph: DomainGraph, db_session: AsyncSession) -> None:
    deps = _deps(db_session, user_id=graph.dater_a.id)
    data = CreateReportData(recipientId=graph.dater_a.id, reason="should fail")
    with pytest.raises(CannotReportSelfError):
        await FileReport.execute(data, db_session, deps)

    # No report and no decision were written for the self pair.
    report = (
        await db_session.execute(select(ProfileReport).where(ProfileReport.reporter_id == graph.dater_a.id))
    ).scalar_one_or_none()
    assert report is None
