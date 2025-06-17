from typing import Any, AsyncGenerator, Dict, List, Optional

import asyncpg
from loguru import logger

from app.core.config import settings


async def get_connection() -> asyncpg.Connection:
    """Get a database connection."""
    conn = await asyncpg.connect(
        user=settings.CLEAN_DB_USER,
        password=settings.CLEAN_DB_PASSWORD,
        host=settings.CLEAN_DB_HOST,
        port=settings.CLEAN_DB_PORT,
        database=settings.CLEAN_DB_NAME,
    )
    return conn


async def get_connection_pool() -> asyncpg.Pool:
    """Get a database connection pool."""
    print(settings.CLEAN_DB_USER)
    print(settings.CLEAN_DB_PORT)
    print(settings.CLEAN_DB_NAME)
    print(settings.CLEAN_DB_PASSWORD)
    print(settings.CLEAN_DB_HOST)
    pool = await asyncpg.create_pool(
        user=settings.CLEAN_DB_USER,
        password=settings.CLEAN_DB_PASSWORD,
        host=settings.CLEAN_DB_HOST,
        port=settings.CLEAN_DB_PORT,
        database=settings.CLEAN_DB_NAME,
    )
    return pool


class Database:
    """Database connection manager."""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Initialize the database connection pool."""
        if self.pool is None:
            try:
                self.pool = await get_connection_pool()
                logger.info("Database connection pool established")
            except Exception as e:
                logger.error(f"Failed to connect to database: {e}")
                raise

    async def disconnect(self) -> None:
        """Close the database connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed")

    async def execute(self, query: str, *args, **kwargs) -> str:
        """Execute a query."""
        if not self.pool:
            await self.connect()
        return await self.pool.execute(query, *args, **kwargs)

    async def fetch(self, query: str, *args, **kwargs) -> List[Dict[str, Any]]:
        """Fetch rows from a query."""
        if not self.pool:
            await self.connect()
        records = await self.pool.fetch(query, *args, **kwargs)
        return [dict(record) for record in records]

    async def fetchval(self, query: str, *args, **kwargs) -> Any:
        """Fetch a single value from a query."""
        if not self.pool:
            await self.connect()
        return await self.pool.fetchval(query, *args, **kwargs)


# Dependency for database access
_db = Database()


async def get_db() -> AsyncGenerator[Database, None]:
    """Get database dependency."""
    try:
        # Ensure we're connected
        await _db.connect()
        yield _db
    finally:
        # Do not disconnect here as we want to reuse the connection pool
        # Disconnection should happen on application shutdown
        pass
