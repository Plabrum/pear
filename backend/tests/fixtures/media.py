from __future__ import annotations

import pytest

from app.config import TestConfig
from app.platform.media.client import LocalMediaClient

__all__ = ["local_media", "media"]


def local_media() -> LocalMediaClient:
    """A LocalMediaClient on the test config — deterministic fake URLs, no AWS."""
    return LocalMediaClient(TestConfig())


@pytest.fixture
def media() -> LocalMediaClient:
    return local_media()
