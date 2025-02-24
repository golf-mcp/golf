"""Simple logging for Redis operations to avoid circular dependencies"""
import logging
from typing import Any, Dict

logger = logging.getLogger("redis")

def log_redis_error(error_type: str, details: Dict[str, Any]) -> None:
    """Log Redis-related errors without depending on the main logging system"""
    logger.error(f"Redis error - {error_type}: {details}") 