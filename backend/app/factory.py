from typing import Any

from advanced_alchemy.extensions.litestar import (
    AsyncSessionConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyPlugin,
)
from litestar import Litestar, Router, get
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
from app.domain.contacts.routes import contacts_router
from app.domain.decisions.routes import decisions_router
from app.domain.discover.routes import discover_router
from app.domain.likes_you.routes import likes_you_router
from app.domain.matches.routes import matches_router
from app.domain.messages.routes import messages_router
from app.domain.photos.routes import photos_router
from app.domain.profiles.routes import profiles_router
from app.domain.prompts.routes import prompts_router
from app.domain.reports.routes import reports_router
from app.domain.wing_pool.routes import wing_pool_router
from app.domain.winger_activity.routes import winger_activity_router
from app.domain.winger_tabs.routes import winger_tabs_router
from app.platform.actions.routes import action_router
from app.platform.auth.middleware import JWTAuthMiddleware
from app.platform.auth.routes import auth_router
from app.platform.base.models import BaseDBModel
from app.platform.base.soft_delete import install_soft_delete_filter
from app.platform.media.routes import media_router
from app.platform.queue.config import queue_config
from app.platform.realtime.routes import realtime_ws
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
# must NOT be rejected by the ES256 middleware for lacking a bearer token. New
# public paths are appended here (e.g. /auth/apple). Note /auth/me and
# /auth/logout are intentionally ABSENT — they require a token.
AUTH_PUBLIC_PATHS = [
    "^/auth/refresh$",
    "^/auth/apple$",
    "^/auth/magic-link/request$",
    "^/auth/magic-link/verify$",
]

# Routes excluded from the auth middleware: health probe, OpenAPI schema/docs,
# the unauthenticated auth routes above, and the websocket route. `/ws`
# authenticates the ES256 token ITSELF (from the `?token=` query param — React
# Native's WebSocket can't set an Authorization header on the handshake), so the
# HTTP bearer middleware must not reject the upgrade for lacking a header.
_AUTH_EXCLUDE = ["^/health", "^/schema", "^/ws", *AUTH_PUBLIC_PATHS]


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
    # multiple replicas — used for presence/messages.
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

    # The mobile app's committed contract serves every data + action endpoint
    # under a `/api` prefix (e.g. GET /api/profiles/me, POST /api/actions/...).
    # Mounting the data and action routers under a single parent
    # `Router(path="/api", ...)` reproduces those paths exactly so the generated
    # read hooks match byte-for-byte.
    #
    # `/health` stays at the root (the platform probe), and `/auth/*` stays at the
    # root (the auth client calls bare `/auth/*`), so neither is remounted.
    api_router = Router(
        path="/api",
        route_handlers=[
            action_router,
            profiles_router,
            contacts_router,
            photos_router,
            prompts_router,
            discover_router,
            wing_pool_router,
            likes_you_router,
            decisions_router,
            matches_router,
            messages_router,
            winger_activity_router,
            winger_tabs_router,
            reports_router,
            media_router,
        ],
    )

    return Litestar(
        route_handlers=[
            health,
            auth_router,
            api_router,
            # Realtime websocket. Stays at the root (`/ws`), not under `/api` — it
            # is a long-lived socket, not an HTTP data/action route, and
            # authenticates its own `?token=` access token (see realtime/routes.py).
            realtime_ws,
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
