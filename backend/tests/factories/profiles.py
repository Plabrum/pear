# Factory for Profile (the base user / auth identity).

from faker import Faker
from polyfactory import Use

from app.domain.profiles.enums import Gender, UserRole
from app.domain.profiles.models import Profile

from .base import BaseFactory

fake = Faker()


class ProfileFactory(BaseFactory):
    __model__ = Profile

    chosen_name = Use(fake.first_name)
    last_name = Use(fake.last_name)
    phone_number = Use(fake.numerify, "+1##########")
    date_of_birth = Use(fake.date_of_birth, minimum_age=22, maximum_age=40)
    gender = Gender.MALE
    avatar_media_id = None
    push_token = None
    # `state` is the user's role (DATER|WINGER) — override for wingers.
    state = UserRole.DATER
