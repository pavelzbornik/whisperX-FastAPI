"""Database fixtures for integration tests."""

from typing import Generator

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


@pytest.fixture(scope="function")
def test_db_engine() -> Generator[Engine, None, None]:
    """Create an in-memory SQLite database engine for testing.

    Uses Alembic migrations to set up the schema.
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # Run Alembic migrations
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", "sqlite:///:memory:")

    # Use the already created engine's connection
    with engine.begin() as connection:
        alembic_cfg.attributes["connection"] = connection
        command.upgrade(alembic_cfg, "head")

    yield engine

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
