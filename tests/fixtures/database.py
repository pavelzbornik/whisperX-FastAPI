"""Database fixtures for integration tests."""

from collections.abc import AsyncGenerator

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import StaticPool

from app.infrastructure.database.models import Base


@pytest_asyncio.fixture(scope="function")
async def test_db_engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create an in-memory async SQLite database engine for testing.

    StaticPool is required for in-memory SQLite so that all connections share
    the same database; NullPool would give each connection its own blank DB.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture(scope="function")
async def db_session(test_db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """
    Create an async database session for testing.

    This fixture creates a new session for each test function and
    automatically rolls back any changes after the test completes.

    Args:
        test_db_engine: The test async database engine

    Yields:
        AsyncSession: A SQLAlchemy async database session
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker

    TestingSessionLocal = async_sessionmaker(
        test_db_engine,
        class_=AsyncSession,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )
    async with TestingSessionLocal() as session:
        try:
            yield session
        finally:
            await session.rollback()
