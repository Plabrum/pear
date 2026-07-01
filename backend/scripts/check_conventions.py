#!/usr/bin/env python3
# Living-code convention guard for the Python backend.
#
# Two checks, both fail the process with a non-zero exit code:
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


def is_exempt(path: Path) -> bool:
    parts = path.parts
    for prefix in EXEMPT_PREFIXES:
        pre = prefix.parts
        # True if `prefix` appears as a contiguous run anywhere in the path, so
        # both "alembic/versions/x.py" and "backend/alembic/versions/x.py" match.
        for i in range(len(parts) - len(pre) + 1):
            if parts[i : i + len(pre)] == pre:
                return True
    return False


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
