"""
Database Context
Stores the shared database instance for handlers.
This is separate from bot_data because Database objects are not picklable.
"""

# Global database instance - set by main.py during startup
_db = None


def set_db(db):
    """Sets the global database instance."""
    global _db
    _db = db


def get_db():
    """Gets the global database instance."""
    return _db
