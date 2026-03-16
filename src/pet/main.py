from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pet.api.exceptions_handler import register_exception_handlers
from pet.api.http_logging import register_http_logging
from pet.api.organizations import organizationsAPI
from pet.config.logging import configure_logging
from pet.config.settings import Settings, get_settings
from pet.infra.sqla.db.connection import create_engine, create_session_maker, ping_engine


def build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        configure_logging(
            level=settings.log_level,
            log_format=settings.log_format,
        )

        engine = create_engine(
            url=settings.dsn,
            echo=settings.engine.echo,
            pool_size=settings.engine.pool_size,
            max_overflow=settings.engine.max_overflow,
        )

        try:
            await ping_engine(engine)
            session_factory = create_session_maker(
                bind=engine,
                autoflush=settings.session_maker.autoflush,
                expire_on_commit=settings.session_maker.expire_on_commit,
            )
        except Exception:
            await engine.dispose()
            raise

        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory

        try:
            yield
        finally:
            await engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    app = FastAPI(lifespan=build_lifespan(resolved_settings))

    include_routers(app)
    register_middlewares(app)
    register_exception_handlers(app)

    return app


def include_routers(app: FastAPI) -> None:
    app.include_router(organizationsAPI)


def register_middlewares(app: FastAPI) -> None:
    register_http_logging(app)
