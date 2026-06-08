import json
from functools import lru_cache
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    PROJECT_NAME: str = "QuantVault"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://qv:qv@localhost:5432/quantvault"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Auth
    SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS — accepts a JSON array OR a comma-separated string so env var
    # dashboards don't require escaped quotes:
    #   ["https://foo.com","https://bar.com"]   ← JSON array
    #   https://foo.com,https://bar.com         ← comma-separated (easier)
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: Any) -> Any:
        if not isinstance(v, str):
            return v
        v = v.strip()
        if not v:
            return []
        try:
            parsed = json.loads(v)
            if isinstance(parsed, list):
                return parsed
        except (json.JSONDecodeError, ValueError):
            pass
        return [origin.strip() for origin in v.split(",") if origin.strip()]

    # Deployment: set USE_CELERY=false on Render to run tasks synchronously
    # (no separate worker process needed). Tasks block the request thread but
    # that's fine for a single-service demo deployment.
    USE_CELERY: bool = True


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — pydantic-settings reads the environment once per process."""
    return Settings()


settings = get_settings()
