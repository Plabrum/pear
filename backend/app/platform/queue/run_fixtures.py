# Standalone CLI to (re)seed the local dev database: `just fixtures`.
#
# Lives in the queue/ infra layer because that is the sanctioned home for engine
# creation, raw `SET LOCAL`, and the system-mode escape. Dev-only — refuses to run
# against production. The demo wipe/seed logic itself lives in app/demo/.

from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import config
from app.demo.seed import seed_dev_fixtures
from app.demo.wipe import wipe_dev_fixtures
from app.utils.discovery import discover_and_import

logger = logging.getLogger(__name__)


async def run_fixtures() -> None:
    """Wipe any prior seed, then seed fresh fixtures — all in one system-mode transaction."""
    if config.ENV == "production":
        raise SystemExit("Refusing to seed: ENV=production")

    # Populate SQLAlchemy metadata so every model/table is known to the session.
    discover_and_import(["models.py", "models/**/*.py"])

    engine = create_async_engine(config.ASYNC_DATABASE_URL)
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    async with sessionmaker() as session:
        async with session.begin():
            await session.execute(text("SET LOCAL app.is_system_mode = true"))
            await wipe_dev_fixtures(session)
            await seed_dev_fixtures(session)

    await engine.dispose()
    logger.info("Fixtures seeded. Sign in via magic link to dev@local.test")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(run_fixtures())
