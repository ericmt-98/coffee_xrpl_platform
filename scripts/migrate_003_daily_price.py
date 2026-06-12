"""
Migration 003: Create daily_prices table.
Run once: python scripts/migrate_003_daily_price.py
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text
from core.database import engine

def migrate():
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS daily_prices (
                id INTEGER PRIMARY KEY,
                price_date DATETIME NOT NULL UNIQUE,
                price_per_kg NUMERIC(10,2) NOT NULL,
                set_by_user_id INTEGER REFERENCES users(id),
                created_at DATETIME
            )
        """))
        conn.commit()
        print("  + Table created: daily_prices")

if __name__ == "__main__":
    print("Running migration 003: daily_prices table...")
    migrate()
    print("Done.")
