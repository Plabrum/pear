"""Litestar application factory.

Adapted from sloopquest's `create_app`, stripped to Pear's Phase-2 surface:

  * SQLAlchemyPlugin (async, shared engine, create_all=False)
  * SAQPlugin (litestar-saq) using the platform queue config; web UI in dev
  * ChannelsPlugin (in-memory backend; presence/messages land in Phase 6)
  * CORSConfig (FRONTEND_ORIGIN) + TemplateConfig (Jinja email templates)
  * Verified ES256 JWT bearer auth excluding ^/health, ^/schema and the
    unauthenticated /auth/* routes (per the auth contract)
  * DI from `get_dependencies()`; registries booted via `discover_and_import`
  * Exception handler mapping `ApplicationError` -> JSON response
  * Routes: /health + the auth router + the actions router. NO domain routers
    yet (Phase 5).

Removed vs sloopquest: organizations, Sqid type codecs + SqidSchemaPlugin,
SessionAuth/Redis session store, billing/comms-webhook/domain routers, the
embeddings queue resolver.
"""

from typing import Any

from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from litestar import Litestar, get
from litestar.channels import ChannelsPlugin
from litestar.channels.backends.memory import MemoryChannelsBackend
from litestar.config.cors import CORSConfig
from litestar.datastructures import State
from litestar.middleware import DefineMiddleware
from litestar.middleware.base import AbstractMiddleware
from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.template.config import TemplateConfig
from litestar_saq import SAQConfig, SAQPlugin
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Config, config
from app.platform.actions.routes import action_router
from app.platform.auth.middleware import JWTAuthMiddleware
from app.platform.auth.routes import auth_router
from app.platform.base.models import BaseDBModel
from app.platform.base.soft_delete import install_soft_delete_filter
from app.platform.queue.config import queue_config
from app.utils.deps import get_dependencies
from app.utils.discovery import discover_and_import
from app.utils.exceptions import ApplicationError, exception_to_http_response

# ── Boot-time registry population ─────────────────────────────────────────────
# Trigger SQLAlchemy mapper registration across all model files.
discover_and_import(["models.py", "models/**/*.py"], base_path="app")
# Trigger @dep registration across all deps.py files (utils + platform + domains).
discover_and_import(["deps.py"], base_path="app")
# Trigger @task / @scheduled_task registration across all tasks.py files.
discover_and_import(["tasks.py"], base_path="app")
# Trigger action group + state machine registration across all domain action files.
discover_and_import(["actions.py", "actions/**/*.py"], base_path="app/domain")

# Hide soft-deleted rows from every SELECT (opt out per-query).
install_soft_delete_filter()

__all__ = ["BaseDBModel", "create_app"]

# Unauthenticated /auth/* routes (the login-method + refresh endpoints). These
# must NOT be rejected by the ES256 middleware for lacking a bearer token. The
# Methods agent appends its new public paths here (e.g. /auth/otp/start). Note
# /auth/me and /auth/logout are intentionally ABSENT — they require a token.
AUTH_PUBLIC_PATHS = [
    "^/auth/refresh$",
    "^/auth/otp/start$",
    "^/auth/otp/check$",
    "^/auth/apple$",
    "^/auth/magic-link/request$",
    "^/auth/magic-link/verify$",
]

# Routes excluded from the auth middleware: health probe, OpenAPI schema/docs,
# and the unauthenticated auth routes above.
_AUTH_EXCLUDE = ["^/health", "^/schema", *AUTH_PUBLIC_PATHS]


@get("/health", sync_to_thread=False, exclude_from_auth=True)
def health() -> dict[str, str]:
    return {"status": "ok"}


def create_app(
    config: Config = config,
    *,
    dependencies_overrides: dict[str, Any] | None = None,
    plugins_overrides: list[Any] | None = None,
    middleware_overrides: list[Any] | None = None,
) -> Litestar:
    """Create and configure the Litestar application."""

    cors_config = CORSConfig(
        allow_origins=[config.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Engine is created explicitly so worker hooks / tasks share the pool config.
    engine = create_async_engine(config.ASYNC_DATABASE_URL)
    async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

    sqlalchemy_plugin = SQLAlchemyPlugin(
        config=SQLAlchemyAsyncConfig(
            engine_instance=engine,
            metadata=BaseDBModel.metadata,
            session_config=AsyncSessionConfig(expire_on_commit=False, autoflush=False),
            create_all=False,
        )
    )

    template_config = TemplateConfig(
        directory=config.EMAIL_TEMPLATES_DIR,
        engine=JinjaTemplateEngine,
    )

    saq_config = SAQConfig(
        queue_configs=queue_config,
        web_enabled=config.IS_DEV,
        use_server_lifespan=True,
    )
    saq_plugin = SAQPlugin(config=saq_config)

    async def _setup_task_queues(app: Litestar) -> None:
        # Exposed for `dispatch_task`'s after-commit enqueue path.
        app.state.task_queues = saq_config.get_queues()

    # Per-process in-memory channels. NOTE: switch to a Redis backend if we run
    # multiple replicas — used for presence/messages in Phase 6.
    channels_plugin = ChannelsPlugin(
        backend=MemoryChannelsBackend(),
        arbitrary_channels_allowed=True,
    )

    default_plugins: list[Any] = [sqlalchemy_plugin, saq_plugin, channels_plugin]
    plugins = plugins_overrides if plugins_overrides is not None else default_plugins

    # Verified ES256 auth: check the Bearer token's signature/exp/iss/aud and attach
    # the verified principal. Skipped for the health probe, OpenAPI schema, and the
    # unauthenticated /auth/* routes (login methods + refresh).
    auth_middleware: AbstractMiddleware | DefineMiddleware = DefineMiddleware(
        JWTAuthMiddleware,
        exclude=_AUTH_EXCLUDE,
    )
    middleware = middleware_overrides if middleware_overrides is not None else [auth_middleware]

    deps = {**get_dependencies(), **(dependencies_overrides or {})}

    on_startup: list[Any] = []
    if plugins_overrides is None:
        on_startup.append(_setup_task_queues)

    return Litestar(
        route_handlers=[
            health,
            auth_router,
            action_router,
        ],
        # The active config is shared via app state so the auth middleware / deps
        # verify with the SAME keypair that signed tokens. In prod every config is
        # built from the same env PEM; under tests `TestConfig` mints an ephemeral
        # keypair, so this single instance must be authoritative everywhere.
        state=State({"config": config}),
        plugins=plugins,
        middleware=middleware,
        cors_config=cors_config,
        template_config=template_config,
        dependencies=deps,
        on_startup=on_startup,
        exception_handlers={ApplicationError: exception_to_http_response},
        debug=config.IS_DEV,
    )
