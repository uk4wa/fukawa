from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    AsyncEngine,
    create_async_engine,
)


def create_engine(
    url: str,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
) -> AsyncEngine:
    return create_async_engine(
        url=url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
    )


def create_session_maker(
    bind: AsyncEngine,
    expire_on_commit: bool = False,
    autoflush: bool = True,
) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(
        bind,
        class_=AsyncSession,
        expire_on_commit=expire_on_commit,
        autoflush=autoflush,
    )
