"""This module provides database connection and session management."""

from collections.abc import Callable, Generator
from functools import wraps
from typing import Any

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

_settings = get_settings()
_db_url = _settings.database.DB_URL
_is_sqlite = _db_url.startswith("sqlite")


def _strip_driver(url: str) -> str:
    """Strip any existing driver qualifier from a DB URL.

    Normalises ``sqlite+aiosqlite://``, ``postgresql+asyncpg://``, etc. back to
    their bare scheme so the caller can unconditionally add the correct driver.
    """
    return (
        url.replace("+aiosqlite", "")
        .replace("+asyncpg", "")
        .replace("+psycopg2", "")
        .replace("postgres://", "postgresql://")
    )


def _make_async_url(url: str) -> str:
    """Convert a DB URL to the correct async-driver URL.

    Handles bare schemes (``sqlite://``, ``postgresql://``) and pre-qualified
    URLs (``sqlite+aiosqlite://``, ``postgresql+asyncpg://``, etc.).
    """
    url = _strip_driver(url)
    if url.startswith("sqlite://"):
        return url.replace("sqlite://", "sqlite+aiosqlite://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _make_sync_url(url: str) -> str:
    """Normalise a DB URL for the sync driver.

    Strips async driver qualifiers and normalises the deprecated ``postgres://``
    scheme to ``postgresql://`` so background-task engines use the correct driver.
    """
    return _strip_driver(url)


_async_db_url = _make_async_url(_db_url)
_sync_db_url = _make_sync_url(_db_url)

# ── Async engine — used by all request-scoped FastAPI handlers ────────────────
# SQLite async: NullPool because SQLite connections are not coroutine-safe.
# PostgreSQL async: standard QueuePool config.
_async_engine_kwargs: dict[str, Any] = {
    "echo": _settings.database.DB_ECHO,
}
if _is_sqlite:
    _async_engine_kwargs["poolclass"] = NullPool
else:
    _async_engine_kwargs["pool_size"] = 15
    _async_engine_kwargs["max_overflow"] = 30
    _async_engine_kwargs["pool_timeout"] = 60
    _async_engine_kwargs["pool_pre_ping"] = True
    _async_engine_kwargs["pool_recycle"] = 300

async_engine = create_async_engine(_async_db_url, **_async_engine_kwargs)

# expire_on_commit=False prevents implicit lazy-loads after commit, which would
# raise MissingGreenlet inside an async context.
AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

# ── Sync engine — kept exclusively for audio_processing_service background tasks ─
# Background tasks run in a thread pool, not on the event loop, so they must use
# the sync driver.
# SQLite sync: NullPool for the same reason as the async engine — SQLite's
# single-writer file lock makes connection pooling harmful.
_sync_connect_args = {"check_same_thread": False} if _is_sqlite else {}
_sync_engine_kwargs: dict[str, Any] = {
    "connect_args": _sync_connect_args,
    "echo": _settings.database.DB_ECHO,
}
if _is_sqlite:
    _sync_engine_kwargs["poolclass"] = NullPool
else:
    _sync_engine_kwargs["pool_size"] = 15
    _sync_engine_kwargs["max_overflow"] = 30
    _sync_engine_kwargs["pool_timeout"] = 60
    _sync_engine_kwargs["pool_pre_ping"] = True
    _sync_engine_kwargs["pool_recycle"] = 300

sync_engine = create_engine(_sync_db_url, **_sync_engine_kwargs)
SyncSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=sync_engine)


def get_db_session() -> Generator[Session, None, None]:
    """Provide a transactional scope around a series of operations."""
    db = SyncSessionLocal()
    try:
        yield db
    finally:
        db.close()


def handle_database_errors(func: Callable[..., Any]) -> Callable[..., Any]:
    """Handle database errors and raise HTTP exceptions."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            error_message = f"Database error: {str(e)}"
            raise HTTPException(status_code=500, detail=error_message)

    return wrapper
