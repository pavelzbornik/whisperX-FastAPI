"""Pytest configuration file for setting up test environment."""

import asyncio
import os

from typing import Generator

import pytest

# Must happen before any app imports — connection.py reads get_settings() at
# module level, so DB_URL must be set before TestContainer triggers that chain.
_test_db_url = os.environ.get("TEST_DB_URL")
if _test_db_url:
    os.environ["DB_URL"] = _test_db_url

from tests.fixtures import TestContainer  # noqa: E402
from tests.fixtures.database import db_session, test_db_engine  # noqa: E402, F401


@pytest.fixture(scope="session", autouse=True)
def setup_test_db(
    tmp_path_factory: pytest.TempPathFactory,
) -> Generator[None, None, None]:
    """
    Session-scoped fixture to set up test database and environment variables.

    This fixture uses pytest's tmp_path_factory to create a temporary database
    file that is automatically cleaned up after the test session.

    Args:
        tmp_path_factory: Pytest fixture for creating temporary paths
    """
    if not os.environ.get("DB_URL"):
        test_db_file = tmp_path_factory.mktemp("db_dir") / "test.db"
        os.environ["DB_URL"] = f"sqlite:///{test_db_file}"
    os.environ["ENVIRONMENT"] = "testing"
    os.environ["DEVICE"] = "cpu"
    os.environ["COMPUTE_TYPE"] = "int8"
    os.environ["WHISPER_MODEL"] = "tiny"
    os.environ["DEFAULT_LANG"] = "en"

    # Import lazily so the engine is created after env vars are set
    from app.core.logging import logger  # noqa: E402
    from app.infrastructure.database.connection import async_engine  # noqa: E402
    from app.infrastructure.database.models import Base  # noqa: E402

    _db_backend = os.environ["DB_URL"].split("://")[0]
    logger.debug(f"conftest.py: DB_URL backend = {_db_backend}")
    logger.debug(f"conftest.py: Async engine dialect = {async_engine.dialect.name}")

    # Create all tables using the async engine, then dispose the pool so that
    # connections created inside asyncio.run()'s temporary event loop are not
    # reused by the test session's event loop (avoids asyncpg "Future attached
    # to a different loop" errors when TEST_DB_URL points at PostgreSQL).
    async def _create_tables() -> None:
        async with async_engine.begin() as conn:
            # Drop first so re-running against an existing external DB (e.g.
            # PostgreSQL via TEST_DB_URL) starts from a clean schema.
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await async_engine.dispose()

    asyncio.run(_create_tables())
    logger.debug("conftest.py: Tables created")

    yield
    # No manual cleanup needed; tmp_path_factory handles it


@pytest.fixture(scope="function")
def test_container() -> Generator[TestContainer, None, None]:
    """
    Provide a test container with mock implementations for testing.

    This fixture creates a TestContainer that overrides production services
    with fast, deterministic mocks. The container is automatically cleaned up
    after each test.

    Yields:
        TestContainer: Container with mock services

    Example:
        >>> def test_with_container(test_container):
        ...     # Use test_container.transcription_service() to get mock
        ...     service = test_container.transcription_service()
        ...     result = service.transcribe(audio, params)
        ...     assert result["text"] == "Mock transcription"
    """
    container = TestContainer()
    yield container
    # Container cleanup happens automatically
