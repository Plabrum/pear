"""Typed dependencies for actions.

`ActionDeps` is the single DI struct every action's `execute`/`is_available`/
`is_disabled` receives. Pear has NO organization concept — scope is relationship
based (dater <-> winger <-> match), so there is no `organization` field and ids
are UUIDs throughout.

The concrete `User`, push, email, and state-machine service types are owned by
other modules (users domain, platform.push, platform.comms, platform.state_machine).
They are imported eagerly (not under TYPE_CHECKING) because Litestar resolves this
dataclass's type hints at request time and must be able to evaluate the field
annotations. The Litestar DI container still resolves the underlying *providers* by
name at request time (see `provide_action_deps`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from litestar import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Config, config

# These symbols are resolvable at runtime (users surface + push + comms +
# state_machine all exist), so they are imported eagerly. This is required because
# Litestar resolves `ActionDeps`'s dataclass type hints at request time via
# `get_type_hints`, which evaluates forward refs in THIS module's namespace — a
# TYPE_CHECKING-only import would raise NameError on every request. `User` is the
# Phase-4 authenticated principal (app.platform.auth.principal.User), re-exported
# from app.domain.users.models for the historical import path the DI resolves by.
from app.domain.users.models import User
from app.platform.actions.registry import ActionRegistry
from app.platform.comms.service.emails import EmailService
from app.platform.push.service import PushService
from app.platform.state_machine.machine import StateMachineService
from app.utils.deps import dep


@dataclass
class ActionDeps:
    """Typed dependencies available to all actions.

    No `organization` — Pear is relationship-scoped, not org-scoped.
    """

    transaction: AsyncSession
    user: User
    request: Request
    config: Config
    push: PushService
    email: EmailService
    state_machine_service: StateMachineService


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
) -> ActionDeps:
    """Assemble `ActionDeps` from request-scoped Litestar dependencies.

    `user`, `push`, `email`, and `state_machine_service` are provided by other
    modules' `@dep(...)` registrations (resolved by name at request time).
    """
    return ActionDeps(
        transaction=transaction,
        request=request,
        config=config,
        user=user,
        push=push,
        email=email,
        state_machine_service=state_machine_service,
    )
