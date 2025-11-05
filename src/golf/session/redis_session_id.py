"""Redis session ID storage - replaces FastMCP's in-memory session._fastmcp_id"""

import contextlib
import os
import redis.asyncio as redis
from uuid import uuid4

class RedisSessionIdHandler:
    """Simple Redis handler for session ID persistence."""
    
    def __init__(self, redis_url: str, redis_password: str | None = None) -> None:
        self.redis_url = redis_url
        self.redis_password = redis_password
        self._redis: redis.Redis | None = None
        self._initialized = False
        
    async def initialize(self) -> bool:
        """Initialize Redis connection with graceful fallback."""
        if self._initialized:
            return self._redis is not None
            
        try:
            self._redis = redis.from_url(
                self.redis_url,
                password=self.redis_password,
                decode_responses=True
            )
            await self._redis.ping()
            self._initialized = True
            return True
        except Exception:
            self._redis = None
            self._initialized = True
            return False
    
    async def get_session_id(self, context_key: str) -> str | None:
        """Get session ID from Redis."""
        if not self._redis:
            return None
        
        try:
            result = await self._redis.get(f"golf:session_id:{context_key}")
            return result if result is not None else None
        except Exception:
            return None  # Graceful degradation
            
    async def store_session_id(self, context_key: str, session_id: str) -> None:
        """Store session ID in Redis with 1 hour TTL."""
        if not self._redis:
            return
        
        with contextlib.suppress(Exception):
            await self._redis.setex(f"golf:session_id:{context_key}", 3600, session_id)
            
    async def generate_and_store_session_id(self, context_key: str) -> str:
        """Generate new session ID and store it."""
        session_id = str(uuid4())
        await self.store_session_id(context_key, session_id)
        return session_id

def is_redis_configured() -> bool:
    """Check if Redis session ID storage is configured."""
    return bool(os.environ.get('PROXY_REDIS_URL'))

def create_redis_handler() -> RedisSessionIdHandler | None:
    """Create Redis session ID handler if configured."""
    redis_url = os.environ.get('PROXY_REDIS_URL')
    if not redis_url:
        return None
        
    redis_password = os.environ.get('PROXY_REDIS_PASSWORD')
    return RedisSessionIdHandler(redis_url, redis_password)