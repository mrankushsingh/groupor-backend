import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.cache import build_cache
from app.config import get_settings
from app.db import database_host_for_logs, engine_error, init_db_with_retries
from app.routers import api, pages

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("groupor")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bind HTTP immediately; Postgres init must never block Railway healthchecks."""
    logger.info(
        "Booting %s on PORT=%s DB=%s",
        settings.site_name,
        os.getenv("PORT", "8000"),
        database_host_for_logs(),
    )
    if os.getenv("RAILWAY_ENVIRONMENT") and "localhost" in (settings.async_database_url or ""):
        logger.error(
            "DATABASE_URL still points at localhost on Railway. "
            "Link PostgreSQL via Variable Reference."
        )

    app.state.db_ready = False
    app.state.db_error = None

    async def _boot_db() -> None:
        try:
            await init_db_with_retries()
            app.state.db_ready = True
            app.state.db_error = None
        except Exception as exc:  # noqa: BLE001
            app.state.db_ready = False
            app.state.db_error = str(exc)
            logger.exception("Postgres init failed permanently: %s", exc)

    task = asyncio.create_task(_boot_db())
    # Yield immediately so uvicorn accepts /healthz while DB connects.
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.site_name,
        docs_url="/api/docs",
        redoc_url=None,
        lifespan=lifespan,
    )
    app.state.cache = build_cache(settings.redis_url)
    app.state.settings = settings
    app.state.db_ready = False
    app.state.db_error = None

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register health BEFORE routers so a router import bug can't hide liveness.
    @app.get("/healthz")
    async def healthz():
        ready = bool(getattr(app.state, "db_ready", False))
        payload = {
            "ok": True,
            "db_ready": ready,
            "db_host": database_host_for_logs(),
            "port": os.getenv("PORT", "8000"),
            "cache": "memory" if not settings.redis_url else "redis-ready",
        }
        err = getattr(app.state, "db_error", None) or engine_error
        if not ready and err:
            payload["db_error"] = str(err)[:500]
        return payload

    static_dir = Path(__file__).resolve().parent / "static"
    static_dir.mkdir(exist_ok=True)
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(api.router)
    app.include_router(pages.router)

    return app


app = create_app()
