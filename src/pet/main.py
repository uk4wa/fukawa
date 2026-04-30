from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
import sqlalchemy as sa
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.types import Lifespan

from pet.api.auth.exception_handlers import register_auth_exception_handlers
from pet.api.exceptions_handler import register_exception_handlers
from pet.api.health import health
from pet.api.middleware.http_logging import register_http_logging
from pet.api.organizations import organizations
from pet.app.auth.verifier import TokenVerifier
from pet.config.logging import configure_logging, get_logger
from pet.config.settings import Settings, get_settings
from pet.di.auth import build_auth_components
from pet.infra.auth.jwks import JwksProvider
from pet.infra.sqla.db.connection import create_engine, create_session_maker

logger = get_logger(__name__)


async def check_db_connection(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.execute(sa.text("SELECT 1"))


def build_lifespan() -> Lifespan[FastAPI]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        settings: Settings = app.state.settings
        engine: AsyncEngine | None = None
        auth_http_client: httpx.AsyncClient | None = None
        jwks: JwksProvider | None = None
        verifier: TokenVerifier | None = getattr(app.state, "token_verifier", None)

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

            if verifier is None:
                auth_http_client, jwks, verifier = await build_auth_components(settings.keycloak)
                app.state.token_verifier = verifier
                logger.info(
                    "auth_initialised",
                    issuer=settings.keycloak.issuer,
                    allowed_algorithms=settings.keycloak.allowed_algorithms,
                )

            logger.info("startup_succeeded")

        except Exception:
            logger.exception("startup_failed")
            if jwks is not None:
                await jwks.aclose()
            elif auth_http_client is not None:
                await auth_http_client.aclose()
            if engine is not None:
                await engine.dispose()
            raise

        try:
            yield
        finally:
            logger.info("shutdown_started")
            try:
                if jwks is not None:
                    await jwks.aclose()
                elif auth_http_client is not None:
                    await auth_http_client.aclose()
            except Exception:
                logger.exception("auth_shutdown_failed")
            try:
                if engine is not None:
                    await engine.dispose()
            except Exception:
                logger.exception("shutdown_failed")
                raise
            logger.info("shutdown_succeeded")

    return lifespan


def create_app(
    settings: Settings | None = None,
    *,
    token_verifier: TokenVerifier | None = None,
) -> FastAPI:
    """Build the FastAPI app.

    `token_verifier` lets tests inject a fake verifier; when provided the
    lifespan skips JWKS discovery.
    """
    resolved_settings = settings or get_settings()

    configure_logging(
        level=resolved_settings.log_level,
        log_format=resolved_settings.log_format,
    )

    app = FastAPI(lifespan=build_lifespan())
    app.state.settings = resolved_settings
    if token_verifier is not None:
        app.state.token_verifier = token_verifier

    app.include_router(health)
    app.include_router(organizations)

    register_exception_handlers(app)
    register_auth_exception_handlers(app)
    register_http_logging(app)

    return app
