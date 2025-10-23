"""Pytest configuration file for setting up test environment."""

import os
import tempfile

# Create a temporary file for the test database
# This allows multiple connections to share the same database
test_db_file = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
test_db_path = test_db_file.name
test_db_file.close()

# Set environment variables before any imports
os.environ["DB_URL"] = f"sqlite:///{test_db_path}"
os.environ["DEVICE"] = "cpu"
os.environ["COMPUTE_TYPE"] = "int8"
os.environ["WHISPER_MODEL"] = "tiny"
os.environ["DEFAULT_LANG"] = "en"

print(f"conftest.py: Setting DB_URL to {os.environ['DB_URL']}")

# Now import the app modules to create tables
from app.infrastructure.database import Base, engine  # noqa: E402

print(f"conftest.py: Engine URL is {engine.url}")

# Create all tables in the test database
Base.metadata.create_all(bind=engine)

print("conftest.py: Tables created")


# Cleanup function to remove the test database file
import atexit


def cleanup_test_db() -> None:
    """Remove the temporary test database file."""
    try:
        os.unlink(test_db_path)
        print(f"conftest.py: Cleaned up test database at {test_db_path}")
    except Exception as e:
        print(f"conftest.py: Failed to cleanup test database: {e}")


atexit.register(cleanup_test_db)
