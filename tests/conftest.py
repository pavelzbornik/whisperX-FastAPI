"""Pytest configuration file for setting up test environment."""

import os

from typing import Generator

import pytest


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
    test_db_file = tmp_path_factory.mktemp("db_dir") / "test.db"
    os.environ["DB_URL"] = f"sqlite:///{test_db_file}"
    os.environ["DEVICE"] = "cpu"
    os.environ["COMPUTE_TYPE"] = "int8"
    os.environ["WHISPER_MODEL"] = "tiny"
    os.environ["DEFAULT_LANG"] = "en"

    # Now import the app modules to create tables
    from app.core.logging import logger  # noqa: E402
    from app.infrastructure.database import Base, engine  # noqa: E402

    logger.debug(f"conftest.py: Setting DB_URL to {os.environ['DB_URL']}")
    logger.debug(f"conftest.py: Engine URL is {engine.url}")

    # Create all tables in the test database
    Base.metadata.create_all(bind=engine)

    logger.debug("conftest.py: Tables created")

    yield
    # No manual cleanup needed; tmp_path_factory handles it
