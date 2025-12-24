"""
Database Pool Manager
Centralized connection pooling for observability routes.
"""

import asyncpg
import os
from typing import Optional
from contextlib import asynccontextmanager

_pool: Optional[asyncpg.Pool] = None


async def init_db_pool() -> asyncpg.Pool:
    """Initialize the database connection pool."""
    global _pool
    if _pool is None:
        database_url = os.environ.get("DATABASE_URL")
        if database_url:
            _pool = await asyncpg.create_pool(
                database_url,
                min_size=2,
                max_size=10,
                command_timeout=60
            )
        else:
            # Fallback to individual params
            _pool = await asyncpg.create_pool(
                host=os.environ.get("DB_HOST", "localhost"),
                port=int(os.environ.get("DB_PORT", 5432)),
                user=os.environ.get("DB_USER", "postgres"),
                password=os.environ.get("DB_PASSWORD", ""),
                database=os.environ.get("DB_NAME", "enterprise_bot"),
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
