# Factory for DatingProfile (a dater's config).

from faker import Faker
from polyfactory import Use

from app.domain.dating_profiles.enums import City, DatingStatus, Interest, Religion
from app.domain.dating_profiles.models import DatingProfile
from app.domain.profiles.enums import Gender

from .base import BaseFactory

fake = Faker()


class DatingProfileFactory(BaseFactory):
    __model__ = DatingProfile

    user_id = None  # set by the caller — one dating profile per user
    bio = Use(fake.sentence, nb_words=12)
    interested_gender = [Gender.MALE, Gender.FEMALE]
    age_from = 24
    age_to = 38
    religion = Religion.AGNOSTIC
    religious_preference = None
    interests = [Interest.TRAVEL, Interest.FOOD, Interest.MUSIC]
    city = City.BOSTON
    is_active = True
    state = DatingStatus.OPEN
