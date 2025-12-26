"""
Database Pool Manager
Centralized async connection pooling for Azure PostgreSQL.

This is the single source for database connections.
Used by: observability, tracing, structured logging.

Usage:
    from core.database import get_db_pool, init_db_pool

    # On startup
    pool = await init_db_pool()

    # Get pool anytime
    pool = await get_db_pool()

    # Context manager for single connection
    async with get_connection() as conn:
        await conn.fetch("SELECT 1")
"""

import logging
import os
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

# Try to import asyncpg
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    ASYNCPG_AVAILABLE = False
    logger.warning("[Database] asyncpg not available")

_pool = None


def _build_connection_string(config: Dict[str, Any] = None) -> str:
    """Build PostgreSQL connection string from env vars or config."""
    # Check for full connection string first
    conn_str = os.getenv("AZURE_PG_CONNECTION_STRING")
    if conn_str:
        return conn_str

    # Build from individual params
    if config:
        db_config = config.get("database", {})
    else:
        db_config = {}

    host = db_config.get("host") or os.getenv("AZURE_PG_HOST", "cogtwin.postgres.database.azure.com")
    port = db_config.get("port") or os.getenv("AZURE_PG_PORT", "5432")
    database = db_config.get("database") or os.getenv("AZURE_PG_DATABASE", "postgres")
    user = db_config.get("user") or os.getenv("AZURE_PG_USER", "mhartigan")
    password = db_config.get("password") or os.getenv("AZURE_PG_PASSWORD", "")
    sslmode = db_config.get("sslmode") or os.getenv("AZURE_PG_SSLMODE", "require")

    return f"postgresql://{user}:{password}@{host}:{port}/{database}?sslmode={sslmode}"


async def init_db_pool(config: Dict[str, Any] = None):
    """Initialize the database connection pool."""
    global _pool

    if not ASYNCPG_AVAILABLE:
        logger.error("[Database] asyncpg not installed - cannot create pool")
        return None

    if _pool is not None:
        return _pool

    try:
        connection_string = _build_connection_string(config)
        _pool = await asyncpg.create_pool(
            connection_string,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
        logger.info("[Database] Connection pool created")
        return _pool
    except Exception as e:
        logger.error(f"[Database] Failed to create pool: {e}")
        raise


async def get_db_pool(config: Dict[str, Any] = None):
    """Get the database connection pool, initializing if needed."""
    global _pool
    if _pool is None:
        await init_db_pool(config)
    return _pool


async def close_db_pool() -> None:
    """Close the database connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
        logger.info("[Database] Connection pool closed")


@asynccontextmanager
async def get_connection(config: Dict[str, Any] = None):
    """Context manager for database connections."""
    pool = await get_db_pool(config)
    if pool is None:
        raise RuntimeError("Database pool not available")
    async with pool.acquire() as conn:
        yield conn
