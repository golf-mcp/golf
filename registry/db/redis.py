import time
import logging
from functools import lru_cache
from urllib.parse import urlparse, urlunparse
from typing import Dict, Any

import redis
from redis import Redis

from ..core.config import get_settings
from .redis_logger import log_redis_error

logger = logging.getLogger(__name__)

@lru_cache()
def create_redis_pool() -> redis.ConnectionPool:
    """Create a singleton Redis connection pool"""
    settings = get_settings()
    
    # Log Redis connection parameters (sanitized)
    redis_url = settings.REDIS_URL
    sanitized_url = redis_url.replace(redis_url.split('@')[-1] if '@' in redis_url else redis_url, 'REDACTED')
    logger.info(f"Creating Redis connection pool with URL (sanitized): {sanitized_url}")
    logger.info(f"Redis DB: {settings.REDIS_DB}")
    
    try:
        parsed = urlparse(settings.REDIS_URL)
        if parsed.scheme == 'redis':
            # Convert redis:// to rediss:// to enable SSL
            parsed = parsed._replace(scheme='rediss')
            redis_url = urlunparse(parsed)
            logger.info("Converting redis:// to rediss:// for SSL support")
        
        host = parsed.hostname
        port = parsed.port or 6379
        logger.info(f"Attempting to connect to Redis at host: {host}, port: {port}")
        # Create connection pool using rediss:// URL for SSL
        pool = redis.ConnectionPool.from_url(redis_url)
        
        logger.info("Successfully created Redis connection pool")
        return pool
    except redis.RedisError as e:
        logger.error(f"Failed to create Redis connection pool: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating Redis pool: {type(e).__name__}: {str(e)}")
        raise

def get_redis_client() -> Redis:
    """Get a Redis client from the connection pool"""
    try:
        logger.info("Getting Redis client from pool")
        pool = create_redis_pool()
        client = Redis(connection_pool=pool)
        
        # Test connection
        try:
            logger.info("Testing Redis connection with ping")
            start_time = time.perf_counter()
            client.ping()
            end_time = time.perf_counter()
            logger.info(f"Redis ping successful in {(end_time - start_time) * 1000:.2f}ms")
        except redis.ConnectionError as e:
            logger.error(f"Redis connection test failed: {str(e)}")
            if isinstance(e, redis.ConnectionError):
                logger.error(f"Connection error details: {e.args}")
            log_redis_error(
                "connection_failed",
                {
                    "url": "REDACTED",
                    "error": str(e),
                    "error_args": getattr(e, 'args', [])
                }
            )
            raise
        except redis.TimeoutError as e:
            logger.error(f"Redis connection test timed out: {str(e)}")
            log_redis_error(
                "connection_timeout",
                {
                    "url": "REDACTED",
                    "error": str(e),
                    "timeout_value": client.connection_pool.connection_kwargs.get('socket_timeout')
                }
            )
            raise
        except Exception as e:
            logger.error(f"Unexpected error testing Redis connection: {type(e).__name__}: {str(e)}")
            log_redis_error(
                "unexpected_error",
                {
                    "url": "REDACTED",
                    "error": str(e),
                    "error_type": type(e).__name__
                }
            )
            raise
            
        return client
    except Exception as e:
        logger.error(f"Failed to get Redis client: {type(e).__name__}: {str(e)}")
        raise 

async def check_redis_health() -> Dict[str, Any]:
    """Check Redis connectivity"""
    try:
        start_time = time.perf_counter()
        client = get_redis_client()
        ping_start = time.perf_counter()
        client.ping()
        ping_duration = round((time.perf_counter() - ping_start) * 1000, 2)
        total_latency = round((time.perf_counter() - start_time) * 1000, 2)
        
        return {
            "status": "healthy",
            "latency_ms": total_latency,
            "ping_latency_ms": ping_duration
        }
    except (redis.ConnectionError, redis.TimeoutError) as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        } 