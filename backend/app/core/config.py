"""Application configuration loaded from environment variables (12-factor)."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # Branding
    LUMIRA_APP_NAME: str = "Lumira"

    # Core
    ENVIRONMENT: str = "development"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    # Comma-separated origins. Kept as a plain string so pydantic-settings doesn't try to
    # JSON-decode it from the environment; use `cors_origins` for the parsed list.
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173"

    # PostgreSQL
    POSTGRES_USER: str = "lumira"
    POSTGRES_PASSWORD: str = "lumira"
    POSTGRES_DB: str = "lumira"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    # S3 / MinIO
    S3_ENDPOINT: str = "http://localhost:9000"
    S3_PUBLIC_ENDPOINT: str = "http://localhost:9000"
    S3_ACCESS_KEY: str = "lumira"
    S3_SECRET_KEY: str = "lumira-secret"
    S3_BUCKET: str = "lumira"
    S3_REGION: str = "us-east-1"
    S3_SECURE: bool = False

    # Seed admin
    FIRST_ADMIN_EMAIL: str = "admin@lumira.dev"
    FIRST_ADMIN_PASSWORD: str = "admin12345"

    # AI engine: stub | vila_m3
    AI_ENGINE: str = "vila_m3"
    VILA_M3_URL: str = "http://localhost:8100"
    VILA_M3_TIMEOUT_SEC: float = 300.0
    VILA_M3_FALLBACK_STUB: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.BACKEND_CORS_ORIGINS.split(",") if o.strip()]

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql+psycopg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def REDIS_URL(self) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{self.REDIS_DB}"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
