from fastapi import FastAPI
from contextlib import asynccontextmanager
from pet.config import get_settings

from pet.infra.sqla.db.connection import create_engine, create_session_maker
from pet.api.exceptions_handler import register_exception_handlers
from pet.api.organizations import organizationsAPI


@asynccontextmanager
async def lifespan(app_: FastAPI):
    settings = get_settings()
    engine = create_engine(
        url=settings.dsn,
        echo=settings.engine.echo,
        pool_size=settings.engine.pool_size,
        max_overflow=settings.engine.max_overflow,
    )
    app_.state.engine = engine
    app_.state.session_factory = create_session_maker(
        bind=engine,
        autoflush=settings.session_maker.autoflush,
        expire_on_commit=settings.session_maker.expire_on_commit,
    )

    yield

    await app_.state.engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(organizationsAPI)

register_exception_handlers(app)
