class BaseRepository:
    """Base class for domain-specific database repositories."""
    def __init__(self, db_manager):
        self.manager = db_manager

    @property
    def conn(self):
        """Always ensures connection is alive before returning."""
        self.manager.ensure_connection()
        return self.manager.conn
