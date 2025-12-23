"""
Database Pool Manager
Provides centralized database connection pooling for observability routes.

Version: 1.0.0
"""

import asyncpg
from typing import Optional
from contextlib import asynccontextmanager
from core.config_loader import get_config

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool
    if _pool is None:
        config = get_config()
        db_config = config.get("database", {})

        _pool = await asyncpg.create_pool(
            host=db_config.get("host", "localhost"),
            port=db_config.get("port", 5432),
            user=db_config.get("user", "postgres"),
            password=db_config.get("password", ""),
            database=db_config.get("database", "enterprise_bot"),
            min_size=2,
            max_size=10,
            command_timeout=60
        )
    return _pool


async def get_db_pool() -> asyncpg.Pool:
    """Get the database connection pool, initializing if needed."""
    global _pool
    if _pool is None:
        await init_db_pool()
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection():
    """Context manager for database connections."""
    pool = await get_db_pool()
    async with pool.acquire() as conn:
        yield conn
