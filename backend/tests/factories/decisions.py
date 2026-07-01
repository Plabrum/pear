# Factory for Decision (likes/passes and winger suggestions).

from app.domain.decisions.enums import DecisionState
from app.domain.decisions.models import Decision

from .base import BaseFactory


class DecisionFactory(BaseFactory):
    __model__ = Decision

    actor_id = None  # set by the caller
    recipient_id = None  # set by the caller — must differ from actor_id
    state = DecisionState.PENDING
    suggested_by = None  # winger id when this is a suggestion
    note = None
