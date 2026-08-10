from functools import lru_cache
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# asyncpg / SQLAlchemy do not understand every libpq query flag Railway may add.
_DROP_QUERY_KEYS = {
    "sslmode",
    "channel_binding",
    "gssencmode",
    "target_session_attrs",
}


def normalize_database_url(url: str) -> str:
    """Railway/Heroku give postgres:// — SQLAlchemy async needs postgresql+asyncpg://."""
    value = (url or "").strip().strip('"').strip("'")
    if not value:
        return value

    if value.startswith("postgres://"):
        value = "postgresql://" + value[len("postgres://") :]
    if value.startswith("postgresql://") and "+asyncpg" not in value:
        value = "postgresql+asyncpg://" + value[len("postgresql://") :]

    parsed = urlparse(value)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    sslmode = (query.get("sslmode") or "").lower()
    for key in list(query):
        if key.lower() in _DROP_QUERY_KEYS or key.lower() == "ssl":
            query.pop(key, None)

    # Keep a simple marker only for our SSL detector; stripped again before connect.
    if sslmode in {"require", "verify-ca", "verify-full", "true", "1"}:
        query["ssl"] = "require"

    return urlunparse(parsed._replace(query=urlencode(query)))


def database_needs_ssl(url: str) -> bool:
    parsed = urlparse(url)
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    ssl = (query.get("ssl") or "").lower()
    host = (parsed.hostname or "").lower()
    if host.endswith(".railway.internal") or host in {"localhost", "127.0.0.1"}:
        return False
    if ssl in {"require", "true", "1"}:
        return True
    # Railway public TCP proxy hosts need TLS.
    if host.endswith(".rlwy.net") or host.endswith(".proxy.rlwy.net") or host.endswith(".railway.app"):
        return True
    return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://groupor:groupor@localhost:5432/groupor"
    site_url: str = "http://localhost:8000"
    site_name: str = "Groupor"
    session_secret: str = "dev-only-change-me"
    page_size: int = 10
    cors_origins: str = "http://localhost:8080,http://localhost:8081,http://localhost:3000"
    redis_url: str = ""

    @property
    def async_database_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    import os

    # On Railway, private networking is more reliable than the public proxy.
    preferred = (
        os.getenv("DATABASE_PRIVATE_URL")
        or os.getenv("DATABASE_URL")
        or os.getenv("POSTGRES_URL")
        or os.getenv("POSTGRESQL_URL")
    )
    if preferred:
        return Settings(database_url=preferred)
    return Settings()
