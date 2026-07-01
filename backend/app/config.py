import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv("../.env.local")
load_dotenv(".env")
load_dotenv("../.env")


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
    # ES256 keypair. Signing key (private) from Secrets Manager; public key verifies.
    JWT_SIGNING_KEY: str = os.getenv("JWT_SIGNING_KEY", "")
    JWT_PUBLIC_KEY: str = os.getenv("JWT_PUBLIC_KEY", "")

    # ─── Twilio (phone OTP — Phase 4) ──────────────────────────────────────────
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_VERIFY_SERVICE_SID: str = os.getenv("TWILIO_VERIFY_SERVICE_SID", "")

    # ─── Apple Sign-In (Phase 4) ───────────────────────────────────────────────
    # Service/app id — the `aud` we validate on Apple identity tokens.
    APPLE_CLIENT_ID: str = os.getenv("APPLE_CLIENT_ID", "")

    # ─── APNs (direct push — Phase 6) ──────────────────────────────────────────
    APNS_KEY: str = os.getenv("APNS_KEY", "")  # .p8 file contents
    APNS_KEY_ID: str = os.getenv("APNS_KEY_ID", "")
    APNS_TEAM_ID: str = os.getenv("APNS_TEAM_ID", "")

    @property
    def IS_DEV(self) -> bool:
        return self.ENV == "development"

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
        if url := os.getenv("ASYNC_DATABASE_URL"):
            return url
        return self._build_db_url(driver="+psycopg")

    @property
    def ADMIN_DB_URL(self) -> str:
        if url := os.getenv("ADMIN_DB_URL"):
            return url
        return self._build_db_url()


@dataclass
class TestConfig(Config):
    """Test environment — points at the test database on port 5435."""

    __test__ = False  # Prevent pytest from collecting this as a test class

    ENV: str = "testing"

    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if url := os.getenv("TEST_ASYNC_DATABASE_URL") or os.getenv("ASYNC_DATABASE_URL"):
            return url
        return self._build_db_url(driver="+psycopg", port="5435")

    @property
    def ADMIN_DB_URL(self) -> str:
        if url := os.getenv("TEST_ADMIN_DB_URL") or os.getenv("ADMIN_DB_URL"):
            return url
        return self._build_db_url(port="5435")


def get_config() -> Config:
    env = os.getenv("ENV", "development")
    if env == "testing":
        return TestConfig()
    return Config()


config = get_config()
