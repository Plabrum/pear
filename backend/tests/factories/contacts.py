# Factory for Contact (the dater ↔ winger relationship).

from faker import Faker
from polyfactory import Use

from app.domain.contacts.enums import WingpersonStatus
from app.domain.contacts.models import Contact

from .base import BaseFactory

fake = Faker()


class ContactFactory(BaseFactory):
    __model__ = Contact

    user_id = None  # the dater — set by the caller
    phone_number = Use(fake.numerify, "+1##########")
    winger_id = None  # set once the invitee accepts
    # Default to an established (ACTIVE) relationship; override for invited/removed.
    state = WingpersonStatus.ACTIVE
