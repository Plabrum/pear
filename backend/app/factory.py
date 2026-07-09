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
from litestar.connection import ASGIConnection
from litestar.middleware.session.server_side import (
    ServerSideSessionBackend,
    ServerSideSessionConfig,
)
from litestar.plugins.jinja import JinjaTemplateEngine
from litestar.security.session_auth import SessionAuth
from litestar.stores.base import Store
from litestar.stores.redis import RedisStore
from litestar.template.config import TemplateConfig
from litestar_saq import SAQConfig, SAQPlugin
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import Config, config
from app.domain.contacts.routes import contacts_router
from app.domain.dating_profiles.routes import dating_profiles_router
from app.domain.decisions.routes import decisions_router
from app.domain.matches.routes import matches_router
from app.domain.messages.routes import messages_router
from app.domain.photos.routes import photos_router
from app.domain.profiles.models import Profile
from app.domain.profiles.routes import profiles_router
from app.domain.prompts.routes import prompts_router
from app.domain.reports.routes import reports_router
from app.platform.actions.routes import action_router
from app.platform.auth.principal import User
from app.platform.auth.routes import auth_router
from app.platform.base.models import BaseDBModel
from app.platform.base.soft_delete import install_soft_delete_filter
from app.platform.media.local_routes import local_media_router
from app.platform.media.routes import media_router
from app.platform.plugins import SqidSchemaPlugin
from app.platform.queue.config import queue_config
from app.platform.realtime.routes import realtime_ws
from app.platform.updates.routes import (
    get_manifest,
    get_manifest_v2,
    get_native_build_fingerprint,
    post_client_event,
    publish_update,
    set_native_build_fingerprint,
)
from app.utils.deps import get_dependencies
from app.utils.discovery import discover_and_import
from app.utils.exceptions import ApplicationError, exception_to_http_response
from app.utils.sqids import Sqid, sqid_dec_hook, sqid_enc_hook, sqid_type_predicate

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

# Unauthenticated /auth/* routes (the login-method endpoints). These must NOT be
# rejected by SessionAuth for lacking a session cookie. New public paths are
# appended here. /auth/me and /auth/logout are intentionally ABSENT — they require
# a session.
AUTH_PUBLIC_PATHS = [
    "^/auth/apple$",
    "^/auth/magic-link/request$",
    "^/auth/magic-link/verify$",
]

# Routes excluded from SessionAuth: health probe, OpenAPI schema/docs, and the
# unauthenticated auth routes above. `/ws` is NOT excluded — SessionAuth runs on
# the upgrade and authenticates the handshake via the session cookie, exposing the
# principal on `conn.user` / `conn.scope["user"]`.
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
    stores_overrides: dict[str, Store] | None = None,
    retrieve_user_handler_override: Any = None,
) -> Litestar:
    """Create and configure the Litestar application."""

    cors_config = CORSConfig(
        allow_origins=[config.FRONTEND_ORIGIN],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization"],
    )

    # Engine is created explicitly so worker hooks / tasks share the pool config,
    # and so the SessionAuth `retrieve_user_handler` can load the principal on its
    # own short-lived session (it runs outside the request-scoped transaction).
    engine = create_async_engine(config.ASYNC_DATABASE_URL)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False, autoflush=False)

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

    default_plugins: list[Any] = [sqlalchemy_plugin, saq_plugin, channels_plugin, SqidSchemaPlugin()]
    plugins = plugins_overrides if plugins_overrides is not None else default_plugins

    async def retrieve_user_handler(session: dict, connection: ASGIConnection) -> User | None:
        """Rehydrate the request principal from the cookie session.

        Reads `session["user_id"]`, loads the Profile by id on a short-lived session
        (the request transaction is not open yet), and returns the `User` principal
        (carrying `.id` for `provide_transaction` + `.role` for ActionDeps). Returns
        None when the session is empty or the profile no longer exists, which makes
        SessionAuth treat the request as unauthenticated.
        """
        user_id = session.get("user_id")
        if not user_id:
            return None
        async with session_factory() as db:
            profile = await db.get(Profile, user_id)
            return User.from_profile(profile) if profile is not None else None

    # Server-side cookie sessions backed by Redis (the infra already runs a redis
    # container). A Redis store — not a memory store — so a rolling deploy / restart
    # does not drop sessions and log everyone out. The signed session id rides a
    # secure, http-only, lax cookie; the payload lives in Redis under the "sessions"
    # store namespace.
    redis_store = RedisStore.with_client(url=config.REDIS_URL)
    stores: dict[str, Store] = {"sessions": redis_store}
    if stores_overrides:
        stores.update(stores_overrides)

    session_auth = SessionAuth[User, ServerSideSessionBackend](
        retrieve_user_handler=retrieve_user_handler_override or retrieve_user_handler,
        session_backend_config=ServerSideSessionConfig(
            store="sessions",
            samesite="lax",
            # Secure everywhere except local dev (== `not config.IS_DEV`); the test
            # config relaxes it so the plain-HTTP test client sends the cookie back.
            secure=config.SESSION_COOKIE_SECURE,
            httponly=True,
            max_age=config.SESSION_MAX_AGE_SECONDS,
        ),
        exclude=_AUTH_EXCLUDE,
    )

    # SessionAuth installs its own middleware via `on_app_init`; tests may still
    # inject extra middleware (or none) through `middleware_overrides`.
    middleware = middleware_overrides if middleware_overrides is not None else []

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
            dating_profiles_router,
            contacts_router,
            photos_router,
            prompts_router,
            decisions_router,
            matches_router,
            messages_router,
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
            # is a long-lived socket, not an HTTP data/action route. It is NOT in the
            # auth exclude list, so SessionAuth runs on the upgrade and authenticates
            # the handshake via the session cookie (see realtime/routes.py).
            realtime_ws,
            # Self-hosted OTA manifest endpoint (Expo Updates protocol v1). Stays at
            # the root (`/updates/manifest`), not under `/api` — `expo-updates` speaks
            # this protocol unauthenticated with its own `expo-*` header set, not a
            # session cookie. `exclude_from_auth=True` on the handler itself opts it
            # out of SessionAuth (see platform/updates/routes.py).
            get_manifest,
            # Plain-JSON, snake_case successor protocol — inert until a custom OTA
            # client calls it. `/updates/manifest` above is untouched and stays live
            # until every installed client has moved off the legacy protocol.
            get_manifest_v2,
            # Client-side observability: the Swift OTA client posts here on download
            # failure, verify failure, apply, and rollback — visible in server logs
            # instead of only discoverable via a support ticket or a device in hand.
            post_client_event,
            # CI-only publish endpoint: `ota.yml` calls this after uploading a bundle
            # to S3 to register the new `app_updates` row. Bearer-token guarded
            # (`requires_updates_publish_token`), not session-auth'd, so it also stays
            # at the root, `exclude_from_auth=True`.
            publish_update,
            # Xcode Cloud write-back / CI read of the latest native build's
            # `@expo/fingerprint` hash (replaces a GitHub Actions variable Xcode
            # Cloud has no automated way to write). POST reuses the same bearer
            # guard as `publish_update`; GET is unauthenticated (not sensitive).
            set_native_build_fingerprint,
            get_native_build_fingerprint,
            # Dev/test only: backs the `LocalMediaClient` presigned `/_local-media/*`
            # URLs with an on-disk sink so uploads round-trip with no S3. The handlers'
            # `requires_local` guard rejects the route in prod.
            local_media_router,
        ],
        plugins=plugins,
        middleware=middleware,
        on_app_init=[session_auth.on_app_init],
        stores=stores,
        cors_config=cors_config,
        template_config=template_config,
        dependencies=deps,
        on_startup=on_startup,
        exception_handlers={ApplicationError: exception_to_http_response},
        type_encoders={Sqid: sqid_enc_hook},
        type_decoders=[(sqid_type_predicate, sqid_dec_hook)],
        debug=config.IS_DEV,
    )
