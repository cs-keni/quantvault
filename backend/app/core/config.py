import json
from functools import lru_cache

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

    # Stored as str so pydantic-settings never tries to JSON-parse it.
    # Use cors_origins property to get list[str]. Accepts either format:
    #   https://foo.com,https://bar.com        ← comma-separated (preferred)
    #   ["https://foo.com","https://bar.com"]  ← JSON array (also works)
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    # Deployment: set USE_CELERY=false on Render to run tasks synchronously
    # (no separate worker process needed). Tasks block the request thread but
    # that's fine for a single-service demo deployment.
    USE_CELERY: bool = True

    @property
    def cors_origins(self) -> list[str]:
        val = self.CORS_ORIGINS.strip()
        if not val:
            return []
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return [str(o) for o in parsed]
        except (json.JSONDecodeError, ValueError):
            pass
        return [o.strip() for o in val.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor — pydantic-settings reads the environment once per process."""
    return Settings()


settings = get_settings()
