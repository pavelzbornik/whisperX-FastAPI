"""Database fixtures for integration tests."""

from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.infrastructure.database.models import Base


@pytest.fixture(scope="function")
def test_db_engine() -> Generator[Engine, None, None]:
    """Create an in-memory SQLite database engine for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_session(test_db_engine: Engine) -> Generator[Session, None, None]:
    """
    Create a database session for testing.

    This fixture creates a new session for each test function and
    automatically rolls back any changes after the test completes.

    Args:
        test_db_engine: The test database engine

    Yields:
        Session: A SQLAlchemy database session
    """
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=test_db_engine
    )
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
