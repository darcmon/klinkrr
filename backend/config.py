from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings

# Placeholder secrets that must never reach production.
KNOWN_DEFAULT_SECRETS = {
    "changemelater",
    "change-me-in-production-use-a-real-secret",
}


class Settings(BaseSettings):
    """
    All app config lives here.
    Values are auto loaded from .env
    Var names are CASE-INSENSITIVE - database_url matches DATABASE_URL in .env
    """

    # "production" turns on the startup checks in production_problems() and
    # secure cookies.
    environment: Literal["development", "production"] = "development"

    # db
    database_url: str = (
        "postgresql+asyncpg://klinkrr:localdev@localhost:5432/klinkrr"
    )

    @field_validator("database_url")
    @classmethod
    def use_asyncpg_driver(cls, url: str) -> str:
        """Accept connection strings as hosts provide them (Render, Neon):
        postgres:// or postgresql:// with libpq options. The app and Alembic
        use the asyncpg driver, which takes `ssl` instead of `sslmode` and
        doesn't accept `channel_binding`."""
        for scheme in ("postgres://", "postgresql://"):
            if url.startswith(scheme):
                url = "postgresql+asyncpg://" + url[len(scheme):]
                break

        parts = urlsplit(url)
        query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key == "sslmode":
                query.append(("ssl", value))
            elif key != "channel_binding":
                query.append((key, value))
        return urlunsplit(parts._replace(query=urlencode(query)))

    # S3 / MinIO
    s3_endpoint_url: str | None = None
    s3_bucket: str = "klinkrr"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "us-east-1"

    # auth
    secret_key: str = "changemelater"
    access_token_expire_minutes: int = 480  # 8hrs

    # CORS
    allowed_origins: str = "http://localhost:5173"

    # admin seed
    admin_email: str = ""
    admin_password: str = ""

    # OAuth
    microsoft_client_id: str = ""
    microsoft_client_secret: str = ""
    microsoft_tenant: str = "common"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_self_serve_enabled: bool = False  # the future flip-switch
    frontend_url: str = "http://localhost:5173"

    # upload limits
    max_upload_size_mb: int = 50
    allowed_file_types: str = "application/pdf, image/png, image/jpeg"

    # cache: in-memory and per process, so run a single API process (see
    # cache_service). Keep it short; it bounds how long a stale version is served.
    cache_ttl_seconds: int = 5

    # audit: public "access" events older than this are deleted by
    # `python -m backend.scripts.prune_audit_logs`. Other events are kept.
    audit_access_retention_days: int = 90

    # external URL safety check
    web_risk_api_key: str = ""

    # fwd to pydantic
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    def production_problems(self) -> list[str]:
        """Settings that are unsafe in production. The app refuses to start
        with any of these; see main.create_app."""
        problems = []
        if self.secret_key in KNOWN_DEFAULT_SECRETS or len(self.secret_key) < 32:
            problems.append(
                "SECRET_KEY must be a random value of at least 32 characters "
                "(e.g. `python -c 'import secrets; print(secrets.token_urlsafe(48))'`)"
            )
        insecure_origins = [
            origin
            for origin in self.allowed_origins_list
            if not origin.startswith("https://") or "localhost" in origin
        ]
        if insecure_origins:
            problems.append(
                f"ALLOWED_ORIGINS must be https and not localhost: {insecure_origins}"
            )
        if not self.frontend_url.startswith("https://"):
            problems.append("FRONTEND_URL must be https")
        if "localdev" in self.database_url or "localhost" in self.database_url:
            problems.append("DATABASE_URL still points at the local development database")
        if not self.aws_access_key_id or not self.aws_secret_access_key:
            problems.append("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required")
        return problems

    # helper
    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",")]

    @property
    def allowed_file_types_list(self) -> list[str]:
        return [t.strip() for t in self.allowed_file_types.split(",")]

    @property
    def max_upload_size_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    """
    Returns a cached Settings instance.
    @lru_cache means this function only runs once — after that,
    it returns the same object every time. This avoids reading
    the .env file on every request.
    """
    return Settings()
