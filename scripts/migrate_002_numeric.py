"""
Migration 002: Document Numeric column changes.

SQLite does not enforce column types strictly, so Python-level Numeric
handling (via SQLAlchemy) is sufficient for existing data. This migration
documents the intent; no ALTER TABLE is needed for SQLite.

If recreating the DB, the new schema (core/models.py) already uses Numeric.
"""

print(
    "Migration 002: Numeric columns\n"
    "SQLite does not enforce column types. SQLAlchemy will handle Decimal\n"
    "conversion in Python automatically with the updated models.py.\n"
    "No ALTER TABLE required. Recreate DB if starting fresh."
)
