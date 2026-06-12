"""
Migration 001: Add login attempt tracking columns to users table.

Run this script once against an existing database:
    python scripts/migrate_001_login_attempts.py

Safe to run multiple times (uses IF NOT EXISTS logic via exception handling).
"""

import os
import sys

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from core.database import engine


def migrate():
    with engine.connect() as conn:
        for column, definition in [
            ("failed_login_count", "INTEGER NOT NULL DEFAULT 0"),
            ("locked_until", "DATETIME"),
        ]:
            try:
                conn.execute(text(f"ALTER TABLE users ADD COLUMN {column} {definition}"))
                conn.commit()
                print(f"  + Added column: users.{column}")
            except Exception:
                print(f"  ~ Column already exists (skipped): users.{column}")


if __name__ == "__main__":
    print("Running migration 001: login attempt tracking...")
    migrate()
    print("Done.")
