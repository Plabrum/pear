from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config, config

# These symbols are imported eagerly (not under TYPE_CHECKING) because Litestar
# resolves `ActionDeps`'s dataclass type hints at request time via `get_type_hints`,
# which evaluates forward refs in THIS module's namespace — a TYPE_CHECKING-only
# import would raise NameError on every request. `User` is the authenticated
# principal (app.platform.auth.principal.User), re-exported from
# app.domain.users.models for the import path the DI resolves by.
from app.domain.users.models import User
from app.platform.actions.registry import ActionRegistry
from app.platform.comms.service.emails import EmailService
from app.platform.media.client import BaseMediaClient
from app.platform.push.service import PushService
from app.platform.realtime.service import RealtimeService
from app.platform.state_machine.machine import StateMachineService
from app.utils.deps import dep


@dataclass
class ActionDeps:
    """Typed dependencies available to all actions."""

    transaction: AsyncSession
    user: User
    request: Request
    config: Config
    push: PushService
    email: EmailService
    state_machine_service: StateMachineService
    # `realtime` and `media` are always injected in production by
    # `provide_action_deps`. They carry `None` defaults ONLY so unit tests that
    # build `ActionDeps` directly and don't exercise the realtime/media paths need
    # not supply them; every request-path construction passes the real services.
    realtime: RealtimeService | None = None
    media: BaseMediaClient | None = None


@dep("action_registry", sync_to_thread=False)
def provide_action_registry() -> ActionRegistry:
    return ActionRegistry()


@dep("action_deps", sync_to_thread=False)
def provide_action_deps(
    transaction: AsyncSession,
    request: Request,
    user: Any,
    push: Any,
    email: Any,
    state_machine_service: Any,
    realtime: Any,
    media: Any,
) -> ActionDeps:
    """Assemble `ActionDeps` from request-scoped Litestar dependencies.

    `user`, `push`, `email`, `state_machine_service`, `realtime`, and `media` are
    provided by other modules' `@dep(...)` registrations (resolved by name at
    request time).
    """
    return ActionDeps(
        transaction=transaction,
        request=request,
        config=config,
        user=user,
        push=push,
        email=email,
        state_machine_service=state_machine_service,
        realtime=realtime,
        media=media,
    )
