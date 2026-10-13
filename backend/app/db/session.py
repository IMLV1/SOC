from collections.abc import AsyncIterator

from sqlalchemy import URL
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


class Database:
    def __init__(self, url: URL) -> None:
        self.engine = create_async_engine(
            url,
            echo=False,
            hide_parameters=True,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
            pool_timeout=3,
            connect_args={
                "timeout": 3,
                "command_timeout": 5,
                "server_settings": {"timezone": "UTC"},
            },
        )
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)

    async def session(self) -> AsyncIterator[AsyncSession]:
        # A new session for every request/job; caller owns the transaction boundary.
        async with self.sessions() as session:
            yield session

    async def close(self) -> None:
        await self.engine.dispose()
