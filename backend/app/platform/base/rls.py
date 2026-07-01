from __future__ import annotations

from typing import Any

from alembic_utils.pg_policy import PGPolicy

from app.domain.decisions.enums import DecisionState
from app.platform.base.models import BaseDBModel

# Global registry of RLS policies — consumed by `alembic/env.py` (register_entities)
# and the test schema builder. Filled by `RLSScopedMixin.__init_subclass__` as each
# model class is imported during the `discover_and_import(["models.py", ...])` scan.
RLS_POLICY_REGISTRY: list[PGPolicy] = []

_WRITES = ("INSERT", "UPDATE", "DELETE")


# ── Predicate algebra ─────────────────────────────────────────────────────────
# A Predicate renders a boolean SQL fragment against a table name. Compose with
# `|`; a bare `str` is accepted anywhere a Predicate is (the raw-SQL escape).


class Predicate:
    def sql(self, table: str) -> str:
        raise NotImplementedError

    def __or__(self, other: Predicate | str) -> Predicate:
        return _Or(self, _coerce(other))


def _coerce(x: Predicate | str) -> Predicate:
    return x if isinstance(x, Predicate) else _Raw(x)


class _Raw(Predicate):
    """Raw SQL escape — the one derived table (`media`) expresses its read this way."""

    def __init__(self, expr: str) -> None:
        self.expr = expr

    def sql(self, table: str) -> str:
        return f"({self.expr})"


class _Or(Predicate):
    def __init__(self, *parts: Predicate) -> None:
        self.parts = parts

    def sql(self, table: str) -> str:
        return "(" + " OR ".join(p.sql(table) for p in self.parts) + ")"


class Owner(Predicate):
    """The row's owner column equals the current actor."""

    def __init__(self, col: str = "user_id") -> None:
        self.col = col

    def sql(self, table: str) -> str:
        return f"{table}.{self.col} = public.current_user_id()"


class OwnerOrWinger(Predicate):
    """The row's owner, or an active wingperson of that owner."""

    def __init__(self, col: str = "user_id") -> None:
        self.col = col

    def sql(self, table: str) -> str:
        return f"({table}.{self.col} = public.current_user_id() OR public.is_active_wingperson({table}.{self.col}))"


class Participants(Predicate):
    """The current actor is one of the row's two party columns."""

    def __init__(self, a: str, b: str) -> None:
        self.a, self.b = a, b

    def sql(self, table: str) -> str:
        return f"public.current_user_id() IN ({table}.{self.a}, {table}.{self.b})"


class ViaMatch(Predicate):
    """The current actor participates in the match the row hangs off."""

    def __init__(self, col: str = "match_id") -> None:
        self.col = col

    def sql(self, table: str) -> str:
        return (
            f"EXISTS (SELECT 1 FROM public.matches m WHERE m.id = {table}.{self.col} "
            f"AND public.current_user_id() IN (m.user_a_id, m.user_b_id))"
        )


class MutualMatchInsert(Predicate):
    """Anti-forgery floor for a self-formed `matches` row.

    Authorizes a participant to insert the pair's match ONLY when both directions
    of their decision are 'approved'. This replaces the old `INSERT: System` rule:
    because RLS itself rejects a forged (non-mutual, or non-participant) pairing,
    the match can be formed in-request — the action no longer needs the system-mode
    escape, and can return the real id instead of a sentinel.
    """

    # The DB literal the decisions `state` TEXT column actually holds for "approved".
    # (TextEnum stores `.name`, so this is "APPROVED" — see rls_functions._ACTIVE_*.)
    _APPROVED = DecisionState.APPROVED.name

    _approved = (
        "EXISTS (SELECT 1 FROM public.decisions d "
        "WHERE d.actor_id = {actor} AND d.recipient_id = {recipient} AND d.state = '{state}')"
    )

    def sql(self, table: str) -> str:
        a, b = f"{table}.user_a_id", f"{table}.user_b_id"
        return (
            f"public.current_user_id() IN ({a}, {b}) "
            f"AND {self._approved.format(actor=a, recipient=b, state=self._APPROVED)} "
            f"AND {self._approved.format(actor=b, recipient=a, state=self._APPROVED)}"
        )


class _Const(Predicate):
    def __init__(self, expr: str) -> None:
        self.expr = expr

    def sql(self, table: str) -> str:
        return self.expr


# Any signed-in actor (public profile content — RLS floor is "are you authenticated").
Authenticated = _Const("public.current_user_id() IS NOT NULL")
# Bearer-secret tables (magic links): the secret itself is the floor, not the actor.
Anyone = _Const("true")
# No user predicate; only `public.is_system_mode()` (OR'd in below) admits the write.
System = _Const("false")


# ── Policy emission ───────────────────────────────────────────────────────────


def _emit(
    table: str,
    suffix: str,
    command: str,
    *,
    using: Predicate | None = None,
    check: Predicate | None = None,
) -> None:
    """Build one `<table>_<suffix>` PGPolicy and append it to the registry.

    Renders `AS PERMISSIVE / FOR <command> / TO pear_app` with `USING` and/or
    `WITH CHECK` set to `public.is_system_mode() OR <predicate>` so trusted
    system/worker operations always pass. Idempotent on (on_entity, signature).
    """
    signature = f"{table}_{suffix}"
    on_entity = f"public.{table}"
    if any(p.on_entity == on_entity and p.signature == signature for p in RLS_POLICY_REGISTRY):
        return

    lines = ["AS PERMISSIVE", f"FOR {command}", "TO pear_app"]
    if using is not None:
        lines.append(f"USING (public.is_system_mode() OR {using.sql(table)})")
    if check is not None:
        lines.append(f"WITH CHECK (public.is_system_mode() OR {check.sql(table)})")

    RLS_POLICY_REGISTRY.append(
        PGPolicy(
            schema="public",
            signature=signature,
            on_entity=on_entity,
            definition="\n        ".join(lines),
        )
    )


def RLSScopedMixin(  # noqa: N802 — factory returning a mixin class
    *,
    read: Predicate | str,
    edit: Predicate | str | dict[str, Predicate | str] = System,
) -> type:
    """Return a mixin that declares a table's RLS, co-located on its model.

    `read` is REQUIRED (fail-closed: a table never ships with a silent public read).
    `edit` defaults to `System` (fail-closed: ordinary users can't write unless a
    scope is granted). `edit` may be a `{command: scope}` dict for tables that grant
    INSERT/UPDATE/DELETE to different parties; omitted commands get no policy (denied).

    Emits one PGPolicy per command (`<table>_select`, `<table>_insert`, …) and
    enrolls the table for FORCE RLS via `metadata.info["rls"]`.
    """

    class _RLSScopedMixin:
        def __init_subclass__(cls, **kwargs: Any) -> None:
            super().__init_subclass__(**kwargs)  # cooperative — chains to SQLAlchemy
            if not hasattr(cls, "__tablename__"):
                return
            table: str = cls.__tablename__  # type: ignore[attr-defined]
            BaseDBModel.metadata.info.setdefault("rls", set()).add(table)

            _emit(table, "select", "SELECT", using=_coerce(read))

            writes = edit if isinstance(edit, dict) else {c: edit for c in _WRITES}
            for command, scope in writes.items():
                pred = _coerce(scope)
                _emit(
                    table,
                    command.lower(),
                    command,
                    using=pred if command in ("UPDATE", "DELETE") else None,
                    check=pred if command in ("INSERT", "UPDATE") else None,
                )

    return _RLSScopedMixin


__all__ = [
    "RLS_POLICY_REGISTRY",
    "Anyone",
    "Authenticated",
    "MutualMatchInsert",
    "Owner",
    "OwnerOrWinger",
    "Participants",
    "Predicate",
    "RLSScopedMixin",
    "System",
    "ViaMatch",
]
