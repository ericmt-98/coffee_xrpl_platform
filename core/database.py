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


def backup_database():
    """Copy the SQLite DB to data/backups/ using sqlite3 backup API (safe while DB is in use).
    Keeps the 10 most recent backups, deletes older ones.
    """
    import sqlite3
    import shutil
    from datetime import datetime, timezone
    from pathlib import Path

    if not os.path.exists(DB_PATH):
        return

    backup_dir = Path(DB_DIR) / "backups"
    backup_dir.mkdir(exist_ok=True)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    dest = backup_dir / f"coffee_platform_{ts}.db"

    src_conn = sqlite3.connect(DB_PATH)
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()

    # Keep latest 10, delete older
    backups = sorted(backup_dir.glob("coffee_platform_*.db"))
    for old in backups[:-10]:
        old.unlink(missing_ok=True)
