# Factories for PromptTemplate, ProfilePrompt and PromptResponse.

from faker import Faker
from polyfactory import Use

from app.domain.prompts.enums import ApprovalState
from app.domain.prompts.models import ProfilePrompt, PromptResponse, PromptTemplate

from .base import BaseFactory

fake = Faker()


class PromptTemplateFactory(BaseFactory):
    __model__ = PromptTemplate

    question = Use(fake.sentence, nb_words=6)


class ProfilePromptFactory(BaseFactory):
    __model__ = ProfilePrompt

    dating_profile_id = None  # set by the caller
    owner_id = None  # the dating profile's dater — set by the caller
    prompt_template_id = None  # set by the caller
    answer = Use(fake.sentence, nb_words=9)


class PromptResponseFactory(BaseFactory):
    __model__ = PromptResponse

    user_id = None  # the author — set by the caller
    profile_owner_id = None  # dater who owns the responded-to prompt — set by the caller
    profile_prompt_id = None  # set by the caller
    message = Use(fake.sentence, nb_words=7)
    state = ApprovalState.PENDING
