"""Application entry point."""

from app.config import config
from app.factory import create_app

app = create_app(config=config)
