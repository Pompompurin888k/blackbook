"""
Blackbook Bot - Centralized Logger
Provides consistent logging across all modules.
"""
import logging
import sys
from datetime import datetime


class BlackbookFormatter(logging.Formatter):
    """Custom formatter with module path and timestamp."""
    
    def format(self, record):
        # Format: [2026-01-23 10:00:00] [handlers.payment] [INFO] - Message
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        level = record.levelname
        
        # Get module path (e.g., handlers.payment)
        module = record.name
        if module.startswith("bot."):
            module = module[4:]  # Remove 'bot.' prefix
        
        return f"[{timestamp}] [{module}] [{level}] - {record.getMessage()}"


def setup_logger(name: str = None, level: int = logging.INFO) -> logging.Logger:
    """
    Sets up a logger with the Blackbook format.
    
    Args:
        name: Logger name (usually __name__)
        level: Logging level (default INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Avoid adding duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(BlackbookFormatter())
        logger.addHandler(handler)
        logger.setLevel(level)
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Gets or creates a logger with the given name.
    Convenience function for modules to use.
    
    Usage:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("STK Push sent to 2547...")
    """
    return setup_logger(name)


# Configure root logger for third-party libraries
def configure_root_logger(level: int = logging.INFO):
    """Configures the root logger with Blackbook formatting."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(BlackbookFormatter())
    root_logger.addHandler(handler)
