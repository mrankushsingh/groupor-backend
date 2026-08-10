import asyncio
import logging
import ssl
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import database_needs_ssl, get_settings

logger = logging.getLogger("groupor.db")


class Base(DeclarativeBase):
    pass


settings = get_settings()
engine: AsyncEngine | None = None
SessionLocal: async_sessionmaker[AsyncSession] | None = None
engine_error: str | None = None


def _build_engine(url: str, *, force_ssl: bool | None = None) -> AsyncEngine:
    use_ssl = database_needs_ssl(url) if force_ssl is None else force_ssl
    parsed = urlparse(url)
    query = {
        k: v
        for k, v in parse_qsl(parsed.query, keep_blank_values=True)
        if k.lower() not in {"ssl", "sslmode"}
    }
    clean = urlunparse(parsed._replace(query=urlencode(query)))
    connect_args: dict = {}
    if use_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        connect_args["ssl"] = ctx
    return create_async_engine(clean, pool_pre_ping=True, connect_args=connect_args)


def ensure_engine(*, force_ssl: bool | None = None) -> AsyncEngine:
    global engine, SessionLocal, engine_error
    if engine is not None and force_ssl is None:
        return engine
    try:
        engine = _build_engine(settings.async_database_url, force_ssl=force_ssl)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        engine_error = None
        return engine
    except Exception as exc:  # noqa: BLE001
        engine = None
        SessionLocal = None
        engine_error = f"{type(exc).__name__}: {exc}"
        logger.exception("Failed to create DB engine: %s", exc)
        raise


def database_host_for_logs() -> str:
    try:
        parsed = urlparse(settings.async_database_url)
        host = parsed.hostname or "?"
        port = parsed.port or 5432
        db = (parsed.path or "/").lstrip("/") or "?"
        return f"{host}:{port}/{db}"
    except Exception:
        return "(unparseable DATABASE_URL)"


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    if SessionLocal is None:
        ensure_engine()
    assert SessionLocal is not None
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    from app import models  # noqa: F401

    eng = ensure_engine()
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def init_db_with_retries(*, attempts: int = 20, delay_seconds: float = 2.0) -> None:
    """Wait for Railway Postgres to accept connections."""
    global engine, SessionLocal

    host = database_host_for_logs()
    logger.info(
        "Connecting to Postgres at %s (ssl=%s)",
        host,
        database_needs_ssl(settings.async_database_url),
    )
    last_error: Exception | None = None

    for attempt in range(1, attempts + 1):
        try:
            if engine is None:
                ensure_engine()
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
            if attempt == 8:
                try:
                    if engine is not None:
                        await engine.dispose()
                except Exception:  # noqa: BLE001
                    pass
                engine = None
                SessionLocal = None
                try:
                    # Flip SSL strategy once.
                    ensure_engine(force_ssl=not database_needs_ssl(settings.async_database_url))
                    logger.warning("Retrying Postgres with flipped SSL=%s", not database_needs_ssl(settings.async_database_url))
                except Exception as rebuild_exc:  # noqa: BLE001
                    last_error = rebuild_exc
                    logger.warning("Engine rebuild failed: %s", rebuild_exc)

            if attempt < attempts:
                await asyncio.sleep(delay_seconds)

    assert last_error is not None
    raise RuntimeError(
        f"Could not connect to Postgres at {host}: {type(last_error).__name__}: {last_error}. "
        "On Railway: use Variable Reference for DATABASE_PRIVATE_URL (or DATABASE_URL)."
    ) from last_error
