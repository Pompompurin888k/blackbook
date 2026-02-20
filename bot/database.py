"""
Facade for backward compatibility.
Delegates all database calls to the new shared domain repositories.
"""
from shared.database import Database as SharedDatabase

class Database:
    def __init__(self):
        self._db = SharedDatabase()
        
    @property
    def conn(self):
        return self._db.manager.conn

    def __getattr__(self, name):
        repos = [
            self._db.providers,
            self._db.payments,
            self._db.verification,
            self._db.portal,
            self._db.safety,
            self._db.analytics,
            self._db.trials,
            self._db.migrations
        ]
        for repo in repos:
            if hasattr(repo, name):
                return getattr(repo, name)
                
        # Fallback to the manager properties/methods
        if hasattr(self._db.manager, name):
            return getattr(self._db.manager, name)
            
        raise AttributeError(f"'Database' object has no attribute '{name}'")
