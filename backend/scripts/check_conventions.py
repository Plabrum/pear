#!/usr/bin/env python3
# Living-code convention guard for the Python backend.
#
# Five checks, all fail the process with a non-zero exit code:
#
#   1. No module-level docstrings. A module that opens with a triple-quoted
#      string reads like ported documentation rather than code that was always
#      here. ast.get_docstring(module) is the reliable signal — it ignores
#      comments and string literals that are not in docstring position.
#
#   2. No internal/provenance references (belt-and-suspenders with the semgrep
#      rules in semgrep/no-internal-references.yml). Catches the same banned
#      words so a local run flags them even when semgrep is not installed.
#
#   3. No request-path system mode (belt-and-suspenders with the semgrep rules in
#      semgrep/no-request-path-system-mode.yml). The trusted RLS-bypass — SET
#      LOCAL app.is_system_mode = true, _enter_system_mode, .system_transition(,
#      resolve_urls_system — is tasks-only: allowed in the worker/task layer
#      (app/platform/queue/**, any tasks.py) and tests, never in a request
#      handler / action / domain query. User actions run under the caller's scope.
#
#   4. No raw statement execution (belt-and-suspenders with the semgrep rule
#      no-raw-sql-execution in semgrep/no-raw-sql.yml). `.execute(text(...))`,
#      `.execute("...")`, `.execute(f"...")` and `.exec_driver_sql(...)` are
#      infra-only: allowed in app/utils/deps.py, app/platform/queue/**,
#      app/platform/base/rls_*.py, any tasks.py and tests. `text(...)` used as a
#      query EXPRESSION (not the direct .execute argument) is not flagged.
#
#   5. No ad-hoc DB engine/session creation (belt-and-suspenders with the semgrep
#      rules no-adhoc-db-engine / no-adhoc-db-sessionmaker). create_async_engine,
#      async_sessionmaker and sessionmaker are wiring-only: allowed in
#      app/config.py, app/factory.py, app/platform/queue/**, app/utils/deps.py
#      and tests. aioboto3.Session() and RotatedSession(...) are different
#      symbols and are not matched.
#
# Run from the backend directory:
#
#     cd backend && uv run python scripts/check_conventions.py
#
# Optional positional args narrow the walk to specific files (used by the
# pre-commit hook to check only staged backend .py files); with no args it walks
# the whole app/ and tests/ trees.

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

# Roots walked when no explicit file arguments are given.
DEFAULT_ROOTS = (Path("app"), Path("tests"))

# Alembic revisions are generated/templated and legitimately carry docstrings and
# revision-history prose, so they are exempt from both checks.
EXEMPT_PREFIXES = (Path("alembic") / "versions",)

# Same banned references as semgrep/no-internal-references.yml. Word boundaries
# keep "ported from" from firing inside "exported from" / "imported from", etc.
REFERENCE_PATTERNS = (
    re.compile(r"\bsloopquest\b", re.IGNORECASE),
    re.compile(r"docs/migration", re.IGNORECASE),
    re.compile(r"\bmigration plan\b", re.IGNORECASE),
    re.compile(r"\bPhase\s+[0-9]", re.IGNORECASE),
    re.compile(r"\b(?:ported|cloned|adapted)\s+from\b", re.IGNORECASE),
)

# Request-path system-mode guard (belt-and-suspenders with
# semgrep/no-request-path-system-mode.yml).
#
# GOVERNING RULE: a user request/action may only create/read/update what the
# caller can reach UNDER THEIR OWN RLS SCOPE. System mode — the trusted RLS
# escape — is ONLY allowed in the worker/task layer and tests, NEVER in a request
# handler / action / domain query.
#
# The patterns target the four system-mode entry points: the SET LOCAL that opens
# the GUC escape (the `= true` literal only — `= false` defensively pins it OFF on
# the request path and is allowed), the `_enter_system_mode` helper, a
# `.system_transition(` call site, and `resolve_urls_system`.
SYSTEM_MODE_PATTERNS = (
    re.compile(r"(?i)set\s+local\s+app\.is_system_mode\s*=\s*true"),
    re.compile(r"\b_enter_system_mode\s*\("),
    re.compile(r"\.system_transition\s*\("),
    re.compile(r"\bresolve_urls_system\b"),
)

# Files/dirs where system mode is legitimate (matched as a contiguous run of path
# parts, so they match whether the walk starts at backend/ or the repo root):
#   * app/platform/queue/**  — the queue/worker transaction layer.
#   * any tasks.py           — the worker task layer.
#   * tests/**               — assert the escape's behavior directly.
SYSTEM_MODE_ALLOWED_DIRS = (
    Path("app") / "platform" / "queue",
    Path("tests"),
)

# Definition sites that only DEFINE the primitives (not request-path uses):
#   * machine.py        — defines the `system_transition` method itself.
#   * rls_functions.py  — defines the SQL `is_system_mode()` function body.
SYSTEM_MODE_EXEMPT_FILES = ("machine.py", "rls_functions.py")

# Raw statement-execution guard (belt-and-suspenders with the semgrep rule
# no-raw-sql-execution in semgrep/no-raw-sql.yml).
#
# GOVERNING RULE: raw transaction-control / statement SQL lives ONLY in the
# reviewed infra/task layer. A request handler / action / domain query must run
# its work through the injected `transaction` dependency, building queries with
# select()/insert()/update() — never raw `.execute(text(...))` / `.execute("...")`
# / `.execute(f"...")` / `.exec_driver_sql(...)`.
#
# PRECISION: `text(...)` used as a query EXPRESSION (inside select()/where()/
# column_property()/Index(postgresql_where=...)) is fine. We only flag `text(...)`
# when it is the DIRECT argument to `.execute(...)`, i.e. `.execute(text(`.
RAW_SQL_PATTERNS = (
    re.compile(r"\.execute\(\s*text\("),
    re.compile(r'\.execute\(\s*f?"'),
    re.compile(r"\.execute\(\s*f?'"),
    re.compile(r"\.exec_driver_sql\s*\("),
)

# Files/dirs where raw statement execution is legitimate (matched as a contiguous
# run of path parts, so they match whether the walk starts at backend/ or the
# repo root). Plus app/utils/deps.py (matched as a path run below) and rls_*.py
# files (the RLS context/comparator internals, matched by filename prefix below).
RAW_SQL_ALLOWED_DIRS = (
    Path("app") / "platform" / "queue",
    Path("tests"),
)
RAW_SQL_ALLOWED_PATHS = (Path("app") / "utils" / "deps.py",)

# Ad-hoc DB engine/session-creation guard (belt-and-suspenders with the semgrep
# rules no-adhoc-db-engine / no-adhoc-db-sessionmaker in semgrep/no-raw-sql.yml).
#
# GOVERNING RULE: SQLAlchemy engine/session-factory construction lives ONLY in
# the wiring layer. A request handler / action / domain query must use the
# injected `transaction` dependency, never its own engine/session.
#
# The patterns target the three SQLAlchemy symbols specifically, so
# `aioboto3.Session()` (AWS) and `RotatedSession(...)` (a dataclass) do not trip.
DB_FACTORY_PATTERNS = (
    re.compile(r"\bcreate_async_engine\s*\("),
    re.compile(r"\basync_sessionmaker\s*\("),
    re.compile(r"\bsessionmaker\s*\("),
)

# Files/dirs where engine/session creation is legitimate. The wiring files are
# matched as contiguous path runs (app/config.py, app/factory.py,
# app/utils/deps.py) so a stray domain config.py never gets exempted.
DB_FACTORY_ALLOWED_DIRS = (Path("app") / "platform" / "queue", Path("tests"))
DB_FACTORY_ALLOWED_PATHS = (
    Path("app") / "config.py",
    Path("app") / "factory.py",
    Path("app") / "utils" / "deps.py",
)


def _path_contains(path: Path, prefix: Path) -> bool:
    """True when `prefix` appears as a contiguous run of parts anywhere in `path`.

    So `app/platform/queue` matches both "app/platform/queue/x.py" and
    "backend/app/platform/queue/x.py" regardless of where the walk started.
    """
    parts = path.parts
    pre = prefix.parts
    for i in range(len(parts) - len(pre) + 1):
        if parts[i : i + len(pre)] == pre:
            return True
    return False


def is_exempt(path: Path) -> bool:
    return any(_path_contains(path, prefix) for prefix in EXEMPT_PREFIXES)


def system_mode_allowed(path: Path) -> bool:
    """True when this file is an allowed home for system mode.

    The worker/task layer (app/platform/queue/**, any tasks.py) and tests, plus
    the definition sites that only DEFINE the primitives rather than reaching them
    from a request.
    """
    if path.name == "tasks.py":
        return True
    if path.name in SYSTEM_MODE_EXEMPT_FILES:
        return True
    return any(_path_contains(path, allowed) for allowed in SYSTEM_MODE_ALLOWED_DIRS)


def check_system_mode(path: Path, source: str) -> list[str]:
    if system_mode_allowed(path):
        return []
    failures: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pattern in SYSTEM_MODE_PATTERNS:
            match = pattern.search(line)
            if match:
                failures.append(
                    f"{path}:{lineno}: request-path system mode {match.group(0)!r} "
                    f"(tasks-only — operate under the caller's RLS scope): {line.strip()}"
                )
    return failures


def raw_sql_allowed(path: Path) -> bool:
    """True when raw statement execution is legitimate in this file.

    The infra/task layer (app/utils/deps.py, app/platform/queue/**, the
    app/platform/base/rls_*.py internals, any tasks.py) and tests.
    """
    if path.name == "tasks.py":
        return True
    if path.name.startswith("rls_") and path.name.endswith(".py"):
        return True
    if any(_path_contains(path, allowed) for allowed in RAW_SQL_ALLOWED_PATHS):
        return True
    return any(_path_contains(path, allowed) for allowed in RAW_SQL_ALLOWED_DIRS)


def check_raw_sql(path: Path, source: str) -> list[str]:
    if raw_sql_allowed(path):
        return []
    failures: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pattern in RAW_SQL_PATTERNS:
            match = pattern.search(line)
            if match:
                failures.append(
                    f"{path}:{lineno}: raw statement execution {match.group(0)!r} "
                    f"(infra-only — run work through the injected transaction dep): {line.strip()}"
                )
    return failures


def db_factory_allowed(path: Path) -> bool:
    """True when DB engine/session-factory construction is legitimate in this file.

    The wiring layer (app/config.py, app/factory.py, app/utils/deps.py,
    app/platform/queue/**) and tests.
    """
    if any(_path_contains(path, allowed) for allowed in DB_FACTORY_ALLOWED_PATHS):
        return True
    return any(_path_contains(path, allowed) for allowed in DB_FACTORY_ALLOWED_DIRS)


def check_db_factory(path: Path, source: str) -> list[str]:
    if db_factory_allowed(path):
        return []
    failures: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pattern in DB_FACTORY_PATTERNS:
            match = pattern.search(line)
            if match:
                failures.append(
                    f"{path}:{lineno}: ad-hoc DB engine/session creation {match.group(0)!r} "
                    f"(wiring-only — use the injected transaction dep): {line.strip()}"
                )
    return failures


def iter_py_files(args: list[str]) -> list[Path]:
    if args:
        return [Path(a) for a in args if a.endswith(".py")]
    files: list[Path] = []
    for root in DEFAULT_ROOTS:
        if root.exists():
            files.extend(sorted(root.rglob("*.py")))
    return files


def check_module_docstring(path: Path, source: str) -> str | None:
    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as exc:
        return f"{path}: could not parse ({exc})"
    if ast.get_docstring(tree) is not None:
        return f"{path}: module has a top-level docstring (not allowed)"
    return None


def check_references(path: Path, source: str) -> list[str]:
    failures: list[str] = []
    for lineno, line in enumerate(source.splitlines(), start=1):
        for pattern in REFERENCE_PATTERNS:
            match = pattern.search(line)
            if match:
                failures.append(f"{path}:{lineno}: banned reference {match.group(0)!r}: {line.strip()}")
    return failures


def main(argv: list[str]) -> int:
    files = iter_py_files(argv)
    failures: list[str] = []

    for path in files:
        if is_exempt(path):
            continue
        try:
            source = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            failures.append(f"{path}: could not read ({exc})")
            continue

        docstring_failure = check_module_docstring(path, source)
        if docstring_failure:
            failures.append(docstring_failure)

        failures.extend(check_references(path, source))
        failures.extend(check_system_mode(path, source))
        failures.extend(check_raw_sql(path, source))
        failures.extend(check_db_factory(path, source))

    if failures:
        print("Convention check FAILED:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(f"\n{len(failures)} violation(s) across {len(files)} file(s).", file=sys.stderr)
        return 1

    print(f"Convention check passed ({len(files)} file(s) scanned).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
