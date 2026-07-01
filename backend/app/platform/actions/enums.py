from enum import StrEnum, auto


class ActionGroupType(StrEnum):
    """Types of action groups.

    Placeholder set — Pear domains register their own action groups here as they
    are implemented (Phase 5). Each domain's `actions.py` adds the member it needs
    and wires it via `action_group_factory`.
    """

    TEST_ACTIONS = auto()
    # Throwaway — registered by tests/fixtures/sample_domain/actions.py (TESTS ONLY)
    # to prove the action registration + is_available gating + OpenAPI exposure
    # path. Not discovered by prod (lives outside app/domain/). Drop in Phase 5.
    SAMPLE_WIDGET_ACTIONS = auto()

    # ── Phase 5 domain action groups ─────────────────────────────────────────
    # Each domain adds the member(s) its actions.py registers via
    # action_group_factory. (profiles is the template; the Integrate stage adds
    # the remaining domains' members.)
    PROFILE_ACTIONS = auto()
    DATING_PROFILE_ACTIONS = auto()
    CONTACT_ACTIONS = auto()
    PHOTO_ACTIONS = auto()
    PROFILE_PROMPT_ACTIONS = auto()
    PROMPT_RESPONSE_ACTIONS = auto()
    DECISION_ACTIONS = auto()
    MESSAGE_ACTIONS = auto()
    REPORT_ACTIONS = auto()


class ActionResultType(StrEnum):
    """Types of follow-up the frontend should perform after action execution."""

    REDIRECT = auto()
    DOWNLOAD_FILE = auto()
    COPY_TO_CLIPBOARD = auto()


class ActionIcon(StrEnum):
    """Icon hints for rendering an action in the client."""

    DEFAULT = auto()
    REFRESH = auto()
    SEND = auto()
    EDIT = auto()
    TRASH = auto()
    ADD = auto()
    CHECK = auto()
    X = auto()
    LINK = auto()
    HEART = auto()
    STAR = auto()
    MESSAGE = auto()
    BLOCK = auto()
