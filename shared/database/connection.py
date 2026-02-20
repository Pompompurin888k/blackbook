import os
import time
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import TRANSACTION_STATUS_INERROR, TRANSACTION_STATUS_UNKNOWN

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """
    Manages the PostgreSQL database connection for both the Web app and the Telegram bot.
    Handles automatic retries, transaction recovery, and healthchecks.
    """
    def __init__(self):
        self.host = os.getenv("DB_HOST", "db")
        self.database = os.getenv("DB_NAME", "blackbook_db")
        self.user = os.getenv("DB_USER", "bb_operator")
        self.password = os.getenv("DB_PASSWORD")
        self.port = os.getenv("DB_PORT", "5432")
        self.db_timezone = os.getenv("DB_TIMEZONE", "Africa/Nairobi")
        self.conn = None
        
        # Open connection initially
        self._connect()

    def _connect(self):
        """Attempts to connect to Postgres. Retries every 2 seconds if DB is still booting."""
        while True:
            try:
                self.conn = psycopg2.connect(
                    host=self.host,
                    database=self.database,
                    user=self.user,
                    password=self.password,
                    port=self.port,
                    options=f"-c timezone={self.db_timezone}",
                    cursor_factory=RealDictCursor
                )
                # By default we do NOT use autocommit for most ops, to allow managed transactions.
                self.conn.autocommit = False
                logger.info(f"✅ Successfully connected to the Blackbook Vault (timezone={self.db_timezone}).")
                return
            except psycopg2.OperationalError:
                logger.info("⏳ Database is booting up... retrying in 2 seconds.")
                time.sleep(2)

    def ensure_connection(self):
        """
        Checks connection health and clears aborted transactions. 
        Ensures a clean, active connection is ready before any query.
        """
        if self.conn is None or self.conn.closed:
            logger.warning("⚠️ Database connection missing/closed. Reconnecting...")
            self._connect()
            return

        try:
            status = self.conn.get_transaction_status()
            if status == TRANSACTION_STATUS_INERROR:
                logger.warning("⚠️ Recovering aborted DB transaction with rollback.")
                self.conn.rollback()
            elif status == TRANSACTION_STATUS_UNKNOWN:
                logger.warning("⚠️ Database transaction state unknown. Reconnecting...")
                self._connect()
                return

            # Probe the connection
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            logger.warning("⚠️ Database connection lost. Reconnecting...")
            self._connect()
        except psycopg2.Error:
            logger.warning("⚠️ DB health probe failed. Rolling back and retrying.")
            try:
                self.conn.rollback()
                with self.conn.cursor() as cur:
                    cur.execute("SELECT 1")
            except psycopg2.Error:
                logger.warning("⚠️ Failed to recover DB connection. Reconnecting...")
                self._connect()

    def healthcheck(self) -> bool:
        """Returns True when DB connection can answer a trivial query."""
        try:
            self.ensure_connection()
            with self.conn.cursor() as cur:
                cur.execute("SELECT 1")
                row = cur.fetchone()
                return bool(row)
        except Exception as e:
            logger.error(f"❌ DB healthcheck failed: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass
            return False
