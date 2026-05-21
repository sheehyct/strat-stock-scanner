"""
Configuration management for STRAT Stock Scanner.

All values are read from environment variables at process start. Secrets are
NEVER baked into a Dockerfile (the deploy uses Railway's NIXPACKS builder, so
secrets are injected at runtime via Railway env vars).
"""

import logging

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # --- Tradier API Configuration ------------------------------------------
    # Single bearer token; production data API.
    TRADIER_API_TOKEN: str
    TRADIER_API_BASE_URL: str = "https://api.tradier.com/v1"
    # Sandbox is reserved for a future toggle (delayed data, paper). v1 of the
    # migration ships production-only; this is read but not surfaced through
    # the request path unless TRADIER_USE_SANDBOX is True AND the sandbox
    # token is present.
    TRADIER_USE_SANDBOX: bool = False
    TRADIER_SANDBOX_TOKEN: str | None = None

    # --- OAuth 2.1 Configuration --------------------------------------------
    JWT_SECRET_KEY: str
    OAUTH_CLIENT_ID: str = "claude-mcp-client"
    OAUTH_CLIENT_SECRET: str | None = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- Rate Limiting Configuration ----------------------------------------
    # Tradier production endpoints are documented at 60-120 req/min/endpoint;
    # we cap below the lower bound as a safety margin.
    RATE_LIMIT_PER_MINUTE: int = 100
    MAX_CONCURRENT_REQUESTS: int = 4

    # --- Server Configuration -----------------------------------------------
    PORT: int = 8080
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"
    SERVER_URL: str = "http://localhost:8080"  # Override with Railway URL in production

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env


settings = Settings()


def configure_logging() -> None:
    """Configure root logging once at process start. Format is structured-ish
    (key=value) so Railway log search works without a JSON parser."""
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


configure_logging()
