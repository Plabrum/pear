from __future__ import annotations

from typing import Any

from app.platform.media.enums import MediaState
from app.platform.media.models import Media
from app.platform.state_machine.machine import State, StateMachine, Transition
from app.platform.state_machine.roles import Role


class PendingState(State[MediaState, Media]):
    value = MediaState.PENDING
    transitions = [
        Transition(to=MediaState.PROCESSING, roles={Role.SYSTEM}),
        # If the move into PROCESSING itself errors, the worker can still fail closed.
        Transition(to=MediaState.FAILED, roles={Role.SYSTEM}),
    ]


class ProcessingState(State[MediaState, Media]):
    value = MediaState.PROCESSING
    transitions = [
        Transition(to=MediaState.READY, roles={Role.SYSTEM}),
        Transition(to=MediaState.FAILED, roles={Role.SYSTEM}),
    ]


class ReadyState(State[MediaState, Media]):
    value = MediaState.READY
    transitions: list[Transition[Any]] = []  # terminal


class FailedState(State[MediaState, Media]):
    value = MediaState.FAILED
    transitions: list[Transition[Any]] = []  # terminal


media_machine = StateMachine[MediaState, Media](
    enum_type=MediaState,
    states={
        MediaState.PENDING: PendingState,
        MediaState.PROCESSING: ProcessingState,
        MediaState.READY: ReadyState,
        MediaState.FAILED: FailedState,
    },
)
