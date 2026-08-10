import asyncio
import logging
import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import database_needs_ssl, get_settings

logger = logging.getLogger("groupor.db")


class Base(DeclarativeBase):
    pass


settings = get_settings()


def _build_engine(url: str):
    clean = url
    connect_args: dict = {}
    if database_needs_ssl(url):
        parsed = urlparse(url)
        query = {
            k: v
            for k, v in parse_qsl(parsed.query, keep_blank_values=True)
            if k.lower() not in {"ssl", "sslmode"}
        }
        clean = urlunparse(parsed._replace(query=urlencode(query)))
        # Railway public certs are valid; CERT_NONE still helps some proxy paths.
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx

    return create_async_engine(clean, pool_pre_ping=True, connect_args=connect_args)


engine = _build_engine(settings.async_database_url)
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


async def init_db_with_retries(*, attempts: int = 20, delay_seconds: float = 2.0) -> None:
    """Wait for Railway Postgres to accept connections."""
    global engine, SessionLocal

    host = database_host_for_logs()
    logger.info("Connecting to Postgres at %s (ssl=%s)", host, database_needs_ssl(settings.async_database_url))
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            await init_db()
            logger.info("Postgres ready (attempt %s/%s)", attempt, attempts)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            logger.warning(
                "Postgres init failed (%s/%s) at %s: %s: %s",
                attempt,
                attempts,
                host,
                type(exc).__name__,
                exc,
            )
            # Rebuild engine mid-way in case first SSL mode was wrong.
            if attempt == 8:
                try:
                    await engine.dispose()
                except Exception:  # noqa: BLE001
                    pass
                alt_url = settings.async_database_url
                # Flip SSL strategy once.
                parsed = urlparse(alt_url)
                if database_needs_ssl(alt_url):
                    # Try without TLS (private-style) by pointing connect_args empty via fake internal hint
                    engine = create_async_engine(
                        urlunparse(
                            parsed._replace(
                                query=urlencode(
                                    {
                                        k: v
                                        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
                                        if k.lower() not in {"ssl", "sslmode"}
                                    }
                                )
                            )
                        ),
                        pool_pre_ping=True,
                    )
                    logger.warning("Retrying Postgres without forced SSL")
                else:
                    ctx = ssl.create_default_context()
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                    engine = create_async_engine(
                        alt_url,
                        pool_pre_ping=True,
                        connect_args={"ssl": ctx},
                    )
                    logger.warning("Retrying Postgres with SSL")
                SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

            if attempt < attempts:
                await asyncio.sleep(delay_seconds)

    assert last_error is not None
    raise RuntimeError(
        f"Could not connect to Postgres at {host}: {type(last_error).__name__}: {last_error}. "
        "On Railway: use the Postgres plugin Variable Reference for DATABASE_URL "
        "(prefer DATABASE_PRIVATE_URL when available)."
    ) from last_error
