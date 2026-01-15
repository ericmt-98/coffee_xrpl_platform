"""
Database connection and session management
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from core.models import Base

# Database file location
DB_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "coffee_platform.db")

# Ensure data directory exists
os.makedirs(DB_DIR, exist_ok=True)

# Create engine
engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,  # Set to True for SQL debugging
    connect_args={"check_same_thread": False}  # Required for SQLite with threads
)

# Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Session = scoped_session(SessionLocal)


def init_database():
    """
    Initialize the database by creating all tables.
    This should be called from the Admin app on first run.
    """
    Base.metadata.create_all(bind=engine)
    return True


def get_session():
    """
    Get a new database session.
    Remember to close the session after use.
    """
    return Session()


def close_session():
    """Close the current session"""
    Session.remove()


def database_exists():
    """Check if the database file exists"""
    return os.path.exists(DB_PATH)
