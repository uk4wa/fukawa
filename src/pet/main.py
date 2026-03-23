from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from pet.api.exceptions_handler import register_exception_handlers
from pet.api.organizations import organizations
from pet.config.settings import Settings, get_settings
from pet.infra.sqla.db.connection import create_engine, create_session_maker


def build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:

        engine = create_engine(
            url=settings.dsn,
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
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        try:
            yield
        finally:
            await app.state.engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    app = FastAPI(lifespan=build_lifespan(resolved_settings))
    app.include_router(organizations)
    register_exception_handlers(app)
    return app
