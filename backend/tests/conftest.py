"""Pytest configuration.

Forces ENV=testing (TestConfig -> port 5435) and QUEUE_SYNC inline before any
app imports, discovers all models so SQLAlchemy metadata is fully populated, then
re-exports every fixture. Mirrors sloopquest's conftest, minus org/Sqid setup.
"""

import os

os.environ.setdefault("ENV", "testing")
# Run queued tasks inline so tests need no live SAQ worker / Redis.
os.environ.setdefault("QUEUE_SYNC", "true")

from app.utils.discovery import discover_and_import  # noqa: E402

discover_and_import(["models.py", "models/**/*.py"])

from tests.fixtures import *  # noqa: E402, F401, F403
