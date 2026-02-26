"""Logging configuration for CollabX server."""
from __future__ import annotations

import logging
import sys
from typing import Any

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)


def get_logger(name: str) -> logging.Logger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def log_event(logger: logging.Logger, event_data: dict[str, Any]) -> None:
    """Log an event in a structured format.
    
    Args:
        logger: Logger instance
        event_data: Event data to log
    """
    logger.info(
        "Event collected",
        extra={
            "event_id": event_data.get("id"),
            "method": event_data.get("method"),
            "path": event_data.get("path"),
            "client_ip": event_data.get("client_ip"),
        }
    )
