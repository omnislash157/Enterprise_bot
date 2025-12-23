"""
Structured Logging - JSON logs with trace correlation

Provides a custom logging handler that writes to PostgreSQL
with trace_id correlation and real-time streaming via NOTIFY.

Usage:
    from core.structured_logging import setup_structured_logging

    # Call once at startup
    setup_structured_logging(db_pool)

    # Then use logging normally - it will be captured
    logger.info("Something happened", extra={'user_id': 123})
"""

import logging
import json
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any, List
from queue import Queue
from dataclasses import dataclass

from core.tracing import get_trace_id, get_current_span

logger = logging.getLogger(__name__)


@dataclass
class LogRecord:
    """Structured log record."""
    timestamp: datetime
    level: str
    logger_name: str
    message: str
    trace_id: Optional[str]
    span_id: Optional[str]
    user_email: Optional[str]
    department: Optional[str]
    session_id: Optional[str]
    endpoint: Optional[str]
    extra: Dict[str, Any]
    exception_type: Optional[str]
    exception_message: Optional[str]
    exception_traceback: Optional[str]


class DatabaseLogHandler(logging.Handler):
    """
    Logging handler that buffers records and writes to PostgreSQL.

    Uses a background thread to avoid blocking the main event loop.
    """

    def __init__(self, buffer_size: int = 100, flush_interval: float = 2.0):
        super().__init__()
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self._buffer: Queue = Queue()
        self._db_pool = None
        self._flush_thread: Optional[threading.Thread] = None
        self._running = False

    def set_db_pool(self, pool):
        """Set the database connection pool and start flushing."""
        self._db_pool = pool
        self._running = True
        self._flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
        self._flush_thread.start()

    def stop(self):
        """Stop the flush thread."""
        self._running = False
        if self._flush_thread:
            self._flush_thread.join(timeout=5)

    def emit(self, record: logging.LogRecord):
        """Handle a log record."""
        try:
            # Get trace context
            trace_id = get_trace_id()
            span = get_current_span()
            span_id = span.span_id if span else None

            # Extract extra fields
            extra = {}
            for key, value in record.__dict__.items():
                if key not in logging.LogRecord.__dict__ and not key.startswith('_'):
                    try:
                        json.dumps(value)  # Check if JSON serializable
                        extra[key] = value
                    except (TypeError, ValueError):
                        extra[key] = str(value)

            # Handle exception info
            exc_type = None
            exc_message = None
            exc_traceback = None
            if record.exc_info:
                exc_type = record.exc_info[0].__name__ if record.exc_info[0] else None
                exc_message = str(record.exc_info[1]) if record.exc_info[1] else None
                exc_traceback = self.format(record) if record.exc_info[2] else None

            log_record = LogRecord(
                timestamp=datetime.utcnow(),
                level=record.levelname,
                logger_name=record.name,
                message=record.getMessage(),
                trace_id=trace_id,
                span_id=span_id,
                user_email=extra.pop('user_email', None),
                department=extra.pop('department', None),
                session_id=extra.pop('session_id', None),
                endpoint=extra.pop('endpoint', None),
                extra=extra,
                exception_type=exc_type,
                exception_message=exc_message,
                exception_traceback=exc_traceback,
            )

            self._buffer.put(log_record)

        except Exception:
            self.handleError(record)

    def _flush_loop(self):
        """Background thread that flushes logs to database."""
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        while self._running:
            try:
                # Collect records from buffer
                records = []
                while not self._buffer.empty() and len(records) < self.buffer_size:
                    try:
                        records.append(self._buffer.get_nowait())
                    except:
                        break

                if records and self._db_pool:
                    loop.run_until_complete(self._write_records(records))

                # Sleep between flushes
                import time
                time.sleep(self.flush_interval)

            except Exception as e:
                print(f"[StructuredLogging] Flush error: {e}")

    async def _write_records(self, records: List[LogRecord]):
        """Write log records to database."""
        try:
            async with self._db_pool.acquire() as conn:
                await conn.executemany("""
                    INSERT INTO enterprise.structured_logs
                    (timestamp, level, logger_name, message, trace_id, span_id,
                     user_email, department, session_id, endpoint, extra,
                     exception_type, exception_message, exception_traceback)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                """, [
                    (r.timestamp, r.level, r.logger_name, r.message, r.trace_id, r.span_id,
                     r.user_email, r.department, r.session_id, r.endpoint,
                     json.dumps(r.extra), r.exception_type, r.exception_message, r.exception_traceback)
                    for r in records
                ])
        except Exception as e:
            print(f"[StructuredLogging] Write error: {e}")


# Global handler instance
_db_handler: Optional[DatabaseLogHandler] = None


def setup_structured_logging(db_pool, level: int = logging.INFO):
    """
    Set up structured logging with database persistence.

    Call this once at application startup after DB pool is created.
    """
    global _db_handler

    # Create handler
    _db_handler = DatabaseLogHandler()
    _db_handler.setLevel(level)
    _db_handler.set_db_pool(db_pool)

    # Add to root logger
    root_logger = logging.getLogger()
    root_logger.addHandler(_db_handler)

    logger.info("[StructuredLogging] Database logging enabled")


def shutdown_structured_logging():
    """Shutdown structured logging (call on app shutdown)."""
    global _db_handler
    if _db_handler:
        _db_handler.stop()
        _db_handler = None
