# Factory for Media (uploaded bytes + processing lifecycle).

from faker import Faker
from polyfactory import Use
from polyfactory.decorators import post_generated

from app.platform.media.enums import MediaState
from app.platform.media.models import Media

from .base import BaseFactory

fake = Faker()


class MediaFactory(BaseFactory):
    __model__ = Media

    owner_id = None  # set by the caller
    file_key = Use(lambda: f"{fake.uuid4()}.jpg")
    mime_type = "image/jpeg"
    file_name = "photo.jpg"
    # Default to a fully-processed READY media so it can back an approved photo.
    state = MediaState.READY

    @post_generated
    @classmethod
    def processed_key(cls, file_key: str) -> str:
        # A full URL (dev seed pointing at an external portrait) is served as-is by
        # LocalMediaClient — keep it verbatim. Otherwise mirror the processed WebP key.
        if file_key.startswith("http"):
            return file_key
        return f"{file_key.rsplit('.', 1)[0]}.webp"
