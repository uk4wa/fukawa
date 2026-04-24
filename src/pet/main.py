from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sqlalchemy as sa
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import Lifespan

from pet.api.exceptions_handler import register_exception_handlers
from pet.api.health import health
from pet.api.middleware.http_logging import register_http_logging
from pet.api.organizations import organizations
from pet.config.logging import configure_logging, get_logger
from pet.config.settings import Settings, get_settings
from pet.infra.sqla.db.connection import create_engine, create_session_maker

logger = get_logger(__name__)


async def check_db_connection(engine: AsyncEngine):
    async with engine.connect() as conn:
        await conn.execute(sa.text("SELECT 1"))


def build_lifespan() -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings: Settings = app.state.settings
        engine: AsyncEngine | None = None

        logger.info(
            "startup_started",
            app_name=settings.app_name,
            pool_size=settings.engine.pool_size,
            max_overflow=settings.engine.max_overflow,
        )
        try:
            engine = create_engine(
                url=settings.db_url,
                echo=settings.engine.echo,
                pool_size=settings.engine.pool_size,
                max_overflow=settings.engine.max_overflow,
                pool_pre_ping=settings.engine.pool_pre_ping,
            )
            session_factory = create_session_maker(
                bind=engine,
                autoflush=settings.session_maker.autoflush,
                expire_on_commit=settings.session_maker.expire_on_commit,
            )
            app.state.engine = engine
            app.state.session_factory = session_factory

            await check_db_connection(engine)

            logger.info("startup_succeeded")

        except Exception:
            logger.exception("startup_failed")
            if engine is not None:
                await engine.dispose()
            raise

        try:
            yield
        finally:
            if engine is not None:
                try:
                    logger.info("shutdown_started")
                    await engine.dispose()
                    logger.info("shutdown_succeeded")
                except Exception:
                    logger.exception("shutdown_failed")
                    raise

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    configure_logging(
        level=resolved_settings.log_level,
        log_format=resolved_settings.log_format,
    )

    app = FastAPI(lifespan=build_lifespan())
    app.state.settings = resolved_settings

    app.include_router(health)
    app.include_router(organizations)

    register_exception_handlers(app)
    register_http_logging(app)

    return app
