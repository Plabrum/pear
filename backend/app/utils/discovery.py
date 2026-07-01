import logging
from importlib import import_module
from pathlib import Path

logger = logging.getLogger(__name__)


def discover_and_import(
    patterns: list[str],
    base_path: str = "app",
    exclude_paths: list[str] | None = None,
) -> list[str]:
    """Discover and import all modules matching the given filename patterns.

    Args:
        patterns: Filename patterns to match (e.g. ["models.py", "models/**/*.py"]).
        base_path: Package directory to search under (default: "app").
        exclude_paths: Path segments to skip (default: __pycache__, test, tests, alembic).

    Returns:
        List of imported module names.
    """
    if exclude_paths is None:
        exclude_paths = ["__pycache__", "test", "tests", "alembic"]

    backend_dir = Path(__file__).parent.parent.parent
    search_dir = backend_dir / base_path

    if not search_dir.exists():
        logger.warning("Search directory does not exist: %s", search_dir)
        return []

    imported: list[str] = []
    seen: set[str] = set()

    for pattern in patterns:
        for file_path in search_dir.rglob(pattern):
            if any(excluded in file_path.parts for excluded in exclude_paths):
                continue
            if file_path.name == "__init__.py":
                continue

            try:
                relative = file_path.relative_to(backend_dir)
                module_name = ".".join((*relative.parts[:-1], relative.stem))

                if module_name in seen:
                    continue

                import_module(module_name)
                imported.append(module_name)
                seen.add(module_name)
                logger.debug("Discovered: %s", module_name)

            except Exception:
                logger.exception("Failed to import discovered module: %s", file_path)

    logger.info("Auto-discovery imported %d modules for patterns %s", len(imported), patterns)
    return imported
