"""This module provides database connection and session management."""

from functools import wraps

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

from .config import Config

# Load environment variables from .env
load_dotenv()

# Create engine and session
DB_URL = Config.DB_URL
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session():
    """Provide a transactional scope around a series of operations."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def handle_database_errors(func):
    """Handle database errors and raise HTTP exceptions."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SQLAlchemyError as e:
            error_message = f"Database error: {str(e)}"
            raise HTTPException(status_code=500, detail=error_message)

    return wrapper
