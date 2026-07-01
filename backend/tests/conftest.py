import os

os.environ.setdefault("ENV", "testing")
# Run queued tasks inline so tests need no live SAQ worker / Redis.
os.environ.setdefault("QUEUE_SYNC", "true")

from app.utils.discovery import discover_and_import  # noqa: E402

discover_and_import(["models.py", "models/**/*.py"])

from tests.fixtures import *  # noqa: E402, F401, F403
