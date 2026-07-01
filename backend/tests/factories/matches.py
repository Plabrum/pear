# Factory for Match (a mutual match record).

from app.domain.matches.models import Match

from .base import BaseFactory


class MatchFactory(BaseFactory):
    __model__ = Match

    # Both set by the caller; the ordered_match_ids CHECK requires user_a_id < user_b_id.
    user_a_id = None
    user_b_id = None
