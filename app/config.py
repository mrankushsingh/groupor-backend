from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    """Railway/Heroku give postgres:// — SQLAlchemy async needs postgresql+asyncpg://."""
    value = (url or "").strip()
    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    if value.startswith("postgresql://") and "+asyncpg" not in value:
        value = "postgresql+asyncpg://" + value[len("postgresql://") :]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://groupor:groupor@localhost:5432/groupor"
    site_url: str = "http://localhost:8000"
    site_name: str = "Groupor"
    session_secret: str = "dev-only-change-me"
    page_size: int = 10
    # Comma-separated browser origins allowed to call /api/* (Vercel frontend).
    cors_origins: str = "http://localhost:8080,http://localhost:8081,http://localhost:3000"
    # Optional — leave empty for now; wire later without changing call sites.
    redis_url: str = ""

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
