# Factory for Message (a chat message in a match).

from faker import Faker
from polyfactory import Use

from app.domain.messages.models import Message

from .base import BaseFactory

fake = Faker()


class MessageFactory(BaseFactory):
    __model__ = Message

    match_id = None  # set by the caller
    sender_id = None  # set by the caller
    body = Use(fake.sentence, nb_words=10)
    is_read = False
