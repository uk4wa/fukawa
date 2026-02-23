from fastapi import FastAPI
from contextlib import asynccontextmanager
from pet.config import get_settings

from pet.infra.sqlalchemy.db.connection import create_engine, create_session_maker
from pet.api.exceptions_handler import register_exception_handlers
from pet.api.organizations import organizationsAPI


@asynccontextmanager
async def lifespan(app_: FastAPI):
    settings = get_settings()
    engine = create_engine(url=settings.dsn)
    app_.state.engine = engine
    app_.state.session_factory = create_session_maker(bind=engine)

    yield

    await app_.state.engine.dispose()


app = FastAPI(lifespan=lifespan)

app.include_router(organizationsAPI)

register_exception_handlers(app)
