import logging

from app.config import config
from app.factory import create_app

# Without this, app.*'s `logging.getLogger(__name__)` calls across the codebase
# have no handler attached (uvicorn's default logging config only sets up the
# "uvicorn"/"uvicorn.access" loggers, not application loggers) and silently
# vanish below WARNING — the actual cause of "no observability" into e.g. the
# /updates/manifest route. This is the single entrypoint both uvicorn (start.sh)
# and the SAQ worker (`litestar workers run`) import, so it covers both.
logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = create_app(config=config)
