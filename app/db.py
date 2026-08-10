import asyncio
import logging
from collections.abc import AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import database_needs_ssl, get_settings

logger = logging.getLogger("groupor.db")


class Base(DeclarativeBase):
    pass


settings = get_settings()
_async_url = settings.async_database_url
_connect_args: dict = {}
if database_needs_ssl(_async_url):
    # Railway public Postgres requires TLS. Prefer connect_args so we don't
    # pass both URL ?ssl= and connect_args ssl= (asyncpg rejects that).
    from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

    parsed = urlparse(_async_url)
    query = {k: v for k, v in parse_qsl(parsed.query, keep_blank_values=True) if k.lower() not in {"ssl", "sslmode"}}
    _async_url = urlunparse(parsed._replace(query=urlencode(query)))
    _connect_args["ssl"] = True

engine = create_async_engine(
    _async_url,
    pool_pre_ping=True,
    connect_args=_connect_args,
)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def database_host_for_logs() -> str:
    try:
        parsed = urlparse(settings.async_database_url)
        return f"{parsed.hostname}:{parsed.port or 5432}/{parsed.path.lstrip('/')}"
    except Exception:
        return "(unparseable DATABASE_URL)"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_db_with_retries(*, attempts: int = 15, delay_seconds: float = 2.0) -> None:
    """Wait for Railway Postgres to accept connections before serving traffic."""
    host = database_host_for_logs()
    logger.info("Connecting to Postgres at %s", host)
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            logger.info("Postgres ready (attempt %s/%s)", attempt, attempts)
            return
        except Exception as exc:  # noqa: BLE001 — surface any connect/auth/ssl failure
            last_error = exc
            logger.warning(
                "Postgres init failed (%s/%s) at %s: %s",
                attempt,
                attempts,
                host,
                exc,
            )
            if attempt < attempts:
                await asyncio.sleep(delay_seconds)
    assert last_error is not None
    raise RuntimeError(
        f"Could not connect to Postgres at {host}. "
        "On Railway: add a PostgreSQL plugin and set DATABASE_URL "
        "(or reference ${{Postgres.DATABASE_URL}})."
    ) from last_error
