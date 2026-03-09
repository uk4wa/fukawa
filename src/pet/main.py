from fastapi import FastAPI
from contextlib import asynccontextmanager
from pet.config import Settings, get_settings
from typing import AsyncIterator


from pet.infra.sqla.db.connection import create_engine, create_session_maker
from pet.api.exceptions_handler import register_exception_handlers
from pet.api.organizations import organizationsAPI


def build_lifespan(settings: Settings):
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:

        engine = create_engine(
            url=settings.dsn,
            echo=settings.engine.echo,
            pool_size=settings.engine.pool_size,
            max_overflow=settings.engine.max_overflow,
        )
        app.state.settings = settings
        app.state.engine = engine
        app.state.session_factory = create_session_maker(
            bind=engine,
            autoflush=settings.session_maker.autoflush,
            expire_on_commit=settings.session_maker.expire_on_commit,
        )
        try:
            yield
        finally:
            await app.state.engine.dispose()

    return lifespan


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    app = FastAPI(lifespan=build_lifespan(resolved_settings))
    app.include_router(organizationsAPI)
    if not resolved_settings.debug:
        register_exception_handlers(app)
    return app
