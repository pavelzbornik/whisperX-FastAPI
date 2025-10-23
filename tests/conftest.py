"""Pytest configuration file for setting up test environment."""

import os

# Set environment variables before any imports
os.environ["DB_URL"] = "sqlite:///:memory:"
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
