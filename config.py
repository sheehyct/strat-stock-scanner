"""
Configuration management for STRAT Stock Scanner
Centralizes all environment variables and settings
"""

from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # Alpaca API Configuration
    ALPACA_API_KEY: str
    ALPACA_API_SECRET: str
    ALPACA_BASE_URL: str = "https://data.alpaca.markets/v2"

    # OAuth 2.1 Configuration
    JWT_SECRET_KEY: str
    OAUTH_CLIENT_ID: str = "claude-mcp-client"
    OAUTH_CLIENT_SECRET: Optional[str] = None
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Rate Limiting Configuration
    ALPACA_REQUESTS_PER_MINUTE: int = 180
    MAX_CONCURRENT_REQUESTS: int = 3

    # Server Configuration
    PORT: int = 8080
    DEBUG: bool = False

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
