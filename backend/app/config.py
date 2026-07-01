import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv("../.env.local")
load_dotenv(".env")
load_dotenv("../.env")


def generate_es256_keypair() -> tuple[str, str]:
    """Generate an ephemeral P-256 (ES256) keypair, returned as (private, public) PEM.

    Used by `TestConfig` so the auth suite can sign + verify real tokens without a
    persisted secret.
    """
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode()
    )
    return private_pem, public_pem


@dataclass
class Config:
    """Application configuration — reads from environment variables."""

    # ─── App ──────────────────────────────────────────────────────────────────
    ENV: str = os.getenv("ENV", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")

    # ─── CORS ─────────────────────────────────────────────────────────────────
    # For Pear this is the mobile app's allowed origins / deep-link scheme. The app
    # talks to the API directly; CORS matters for the web build (`npm run web`).
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:8081")

    # ─── Redis ────────────────────────────────────────────────────────────────
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # ─── Queue ────────────────────────────────────────────────────────────────
    QUEUE_SYNC: bool = os.getenv("QUEUE_SYNC", "").lower() in {"1", "true", "yes"}

    # ─── AWS ──────────────────────────────────────────────────────────────────
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")

    # ─── S3 ───────────────────────────────────────────────────────────────────
    S3_MEDIA_BUCKET: str = os.getenv("S3_MEDIA_BUCKET", "pear-media")

    # ─── Email templates ──────────────────────────────────────────────────────
    EMAIL_TEMPLATES_DIR: str = os.getenv("EMAIL_TEMPLATES_DIR", "email_templates")

    # ─── SES / email ──────────────────────────────────────────────────────────
    # ENV=local selects the LocalEmailClient (logs instead of sends); prod selects SESEmailClient.
    SES_REGION: str = os.getenv("SES_REGION", os.getenv("AWS_REGION", "us-east-1"))
    SES_CONFIGURATION_SET: str = os.getenv("SES_CONFIGURATION_SET", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@pear.local")

    # ─── JWT (we issue our own tokens — Phase 4) ───────────────────────────────
    # ES256 keypair (PEM). Signing key (private) from Secrets Manager; public key
    # verifies. In tests `TestConfig` generates an ephemeral keypair so no real
    # secret is needed (see `TestConfig.__post_init__`).
    JWT_SIGNING_KEY: str = os.getenv("JWT_SIGNING_KEY", "")
    JWT_PUBLIC_KEY: str = os.getenv("JWT_PUBLIC_KEY", "")
    # Access token lifetime (~15m) and the `iss`/`aud` we stamp + verify.
    ACCESS_TOKEN_TTL_SECONDS: int = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "900"))
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "pear")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "pear-app")
    # Refresh token lifetime (opaque, rotating, server-side stored). Default 30d.
    REFRESH_TOKEN_TTL_SECONDS: int = int(os.getenv("REFRESH_TOKEN_TTL_SECONDS", str(60 * 60 * 24 * 30)))

    # ─── Twilio (phone OTP — Phase 4) ──────────────────────────────────────────
    # In local/testing these are unused — `LocalOtpClient` is selected instead and
    # accepts a fixed dev code (`DEV_OTP_CODE`).
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_VERIFY_SERVICE_SID: str = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")
    # Fixed code the LocalOtpClient accepts for any phone in local/testing.
    DEV_OTP_CODE: str = os.getenv("DEV_OTP_CODE", "000000")

    # ─── Apple Sign-In (Phase 4) ───────────────────────────────────────────────
    # Service/app id — the `aud` we validate on Apple identity tokens.
    APPLE_CLIENT_ID: str = os.getenv("APPLE_CLIENT_ID", "")
    # Apple OIDC issuer + JWKS endpoint (overridable so tests can inject a key).
    APPLE_ISSUER: str = os.getenv("APPLE_ISSUER", "https://appleid.apple.com")
    APPLE_JWKS_URL: str = os.getenv("APPLE_JWKS_URL", "https://appleid.apple.com/auth/keys")
    # Test/dev escape hatch: a PEM public key that verifies locally-signed Apple
    # tokens (bypasses the JWKS fetch). Empty in prod — JWKS is used.
    APPLE_TEST_PUBLIC_KEY: str = os.getenv("APPLE_TEST_PUBLIC_KEY", "")

    # ─── Magic link (email login — Phase 4) ────────────────────────────────────
    # Public base URL of the API; the GET verify hop 302s into the app scheme.
    API_BASE_URL: str = os.getenv("API_BASE_URL", "http://localhost:8000")
    # App deep-link scheme target for the email-link return hop.
    APP_DEEP_LINK_SCHEME: str = os.getenv("APP_DEEP_LINK_SCHEME", "pear")
    # Magic-link token TTL (one-time, single-use). Default 15m.
    MAGIC_LINK_TTL_SECONDS: int = int(os.getenv("MAGIC_LINK_TTL_SECONDS", str(60 * 15)))
    # Dev bypass: this email logs in instantly without sending mail (empty = off).
    DEV_MAGIC_LINK_EMAIL: str = os.getenv("DEV_MAGIC_LINK_EMAIL", "")

    # ─── APNs (direct push — Phase 6) ──────────────────────────────────────────
    APNS_KEY: str = os.getenv("APNS_KEY", "")  # .p8 file contents
    APNS_KEY_ID: str = os.getenv("APNS_KEY_ID", "")
    APNS_TEAM_ID: str = os.getenv("APNS_TEAM_ID", "")

    @property
    def IS_DEV(self) -> bool:
        return self.ENV == "development"

    # ─── Database roles (sloopquest non-superuser model) ───────────────────────
    # Two distinct roles, two distinct URLs:
    #   * the APP role (`DB_APP_USER`, default `pear_app`) is a NON-superuser,
    #     NON-owner LOGIN role the runtime (API requests, worker tasks, websockets)
    #     connects as. Being a non-owner, it is natively subject to FORCE RLS — RLS
    #     is the real authorization floor. `ASYNC_DATABASE_URL` uses it.
    #   * the ADMIN/owner role (`DB_USER`, default `postgres`) owns the schema and
    #     runs Alembic migrations (including creating `pear_app` + its grants).
    #     `ADMIN_DB_URL` uses it.
    DB_APP_USER: str = os.getenv("DB_APP_USER", "pear_app")
    DB_APP_PASSWORD: str = os.getenv("DB_APP_PASSWORD", "pear_app")

    def _build_db_url(
        self,
        driver: str = "",
        user: str | None = None,
        password: str | None = None,
        port: str | None = None,
    ) -> str:
        endpoint = os.getenv("DB_ENDPOINT", "localhost")
        port = port or os.getenv("DB_PORT", "5432")
        name = os.getenv("DB_NAME", "pear")
        user = user or os.getenv("DB_USER", "postgres")
        password = password or os.getenv("DB_PASSWORD", "postgres")
        return f"postgresql{driver}://{user}:{password}@{endpoint}:{port}/{name}"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """App-runtime URL — connects as the NON-superuser `pear_app` role."""
        if url := os.getenv("ASYNC_DATABASE_URL"):
            return url
        return self._build_db_url(driver="+psycopg", user=self.DB_APP_USER, password=self.DB_APP_PASSWORD)

    @property
    def ADMIN_DB_URL(self) -> str:
        """Migration/owner URL — connects as the admin role (`DB_USER`)."""
        if url := os.getenv("ADMIN_DB_URL"):
            return url
        return self._build_db_url()


@dataclass
class TestConfig(Config):
    """Test environment — points at the test database on port 5435.

    Generates an ephemeral ES256 keypair on construction (unless one is supplied
    via env) so the auth suite signs/verifies real tokens without a real secret.
    """

    __test__ = False  # Prevent pytest from collecting this as a test class

    ENV: str = "testing"

    def __post_init__(self) -> None:
        if not self.JWT_SIGNING_KEY or not self.JWT_PUBLIC_KEY:
            private_pem, public_pem = generate_es256_keypair()
            self.JWT_SIGNING_KEY = private_pem
            self.JWT_PUBLIC_KEY = public_pem

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        # App-runtime URL: the NON-superuser `pear_app` role on the test DB (5435),
        # so the RLS suite is enforced for real (no superuser bypass).
        if url := os.getenv("TEST_ASYNC_DATABASE_URL") or os.getenv("ASYNC_DATABASE_URL"):
            return url
        return self._build_db_url(driver="+psycopg", user=self.DB_APP_USER, password=self.DB_APP_PASSWORD, port="5435")

    @property
    def ADMIN_DB_URL(self) -> str:
        # Migration/owner URL: the admin (`postgres`) role on the test DB (5435).
        if url := os.getenv("TEST_ADMIN_DB_URL") or os.getenv("ADMIN_DB_URL"):
            return url
        return self._build_db_url(port="5435")


def get_config() -> Config:
    env = os.getenv("ENV", "development")
    if env == "testing":
        return TestConfig()
    return Config()


config = get_config()
