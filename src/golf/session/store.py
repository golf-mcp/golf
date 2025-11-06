"""Redis-backed session storage for Golf MCP servers"""

import contextlib
import os
import pickle
import asyncio
from typing import Any
from contextlib import suppress
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


class RedisSessionStorage:
    """Redis-backed dictionary replacement for _server_instances"""
    
    def __init__(self, redis_handler: RedisSessionIdHandler) -> None:
        self.redis = redis_handler
        self._cache: dict[str, Any] = {}  # Local cache for performance
        self._cache_ttl = 300  # 5 minutes local cache TTL
        self._cache_timestamps: dict[str, float] = {}
    
    def __contains__(self, session_id: str) -> bool:
        """Check if session exists in cache or Redis"""
        # Check local cache first
        if self._is_cached(session_id):
            return True
        
        # Check Redis
        if not self.redis._redis:
            return False
        
        try:
            # Use asyncio.run for sync interface compatibility
            exists_coroutine = self.redis._redis.exists(f"golf:session_obj:{session_id}")
            result = asyncio.run(exists_coroutine)  # type: ignore
            return bool(result)
        except Exception:
            return False
    
    def __getitem__(self, session_id: str) -> Any:
        """Get session transport object from cache or Redis"""
        # Try cache first
        if self._is_cached(session_id):
            return self._cache[session_id]
        
        # Try Redis
        if not self.redis._redis:
            raise KeyError(session_id)
        
        try:
            # Retrieve serialized session from Redis
            get_coroutine = self.redis._redis.get(f"golf:session_obj:{session_id}")
            data = asyncio.run(get_coroutine)  # type: ignore
            if data is None:
                raise KeyError(session_id)
            
            # Deserialize session transport object
            session_transport = pickle.loads(data.encode('latin1'))
            
            # Update local cache
            self._cache[session_id] = session_transport
            import time
            self._cache_timestamps[session_id] = time.time()
            
            return session_transport
        except Exception as e:
            if isinstance(e, KeyError):
                raise
            # For other errors, treat as missing
            raise KeyError(session_id) from e
    
    def __setitem__(self, session_id: str, transport_obj: Any) -> None:
        """Store session transport object in cache and Redis"""
        # Store in local cache
        self._cache[session_id] = transport_obj
        import time
        self._cache_timestamps[session_id] = time.time()
        
        # Store in Redis
        if self.redis._redis:
            try:
                # Serialize session transport object
                serialized = pickle.dumps(transport_obj).decode('latin1')
                
                # Store in Redis with TTL (1 hour)
                setex_coroutine = self.redis._redis.setex(
                    f"golf:session_obj:{session_id}", 
                    3600, 
                    serialized
                )
                asyncio.run(setex_coroutine)  # type: ignore
            except Exception:
                # Graceful degradation - keep in local cache only
                pass
    
    def __delitem__(self, session_id: str) -> None:
        """Remove session from cache and Redis"""
        # Remove from local cache
        self._cache.pop(session_id, None)
        self._cache_timestamps.pop(session_id, None)
        
        # Remove from Redis
        if self.redis._redis:
            with suppress(Exception):
                delete_coroutine = self.redis._redis.delete(f"golf:session_obj:{session_id}")
                asyncio.run(delete_coroutine)  # type: ignore
    
    def get(self, session_id: str, default: Any = None) -> Any:
        """Dict-compatible get method"""
        try:
            return self[session_id]
        except KeyError:
            return default
    
    def keys(self) -> set[str]:
        """Return all session IDs (for compatibility)"""
        if not self.redis._redis:
            return set(self._cache.keys())
        
        try:
            # Get all Redis keys matching our pattern
            keys_coroutine = self.redis._redis.keys("golf:session_obj:*")
            redis_keys = asyncio.run(keys_coroutine)  # type: ignore
            # Extract session IDs from Redis keys
            redis_session_ids = [key.replace("golf:session_obj:", "") for key in redis_keys]
            # Combine with local cache keys
            all_keys = set(redis_session_ids) | set(self._cache.keys())
            return all_keys
        except Exception:
            return set(self._cache.keys())
    
    def _is_cached(self, session_id: str) -> bool:
        """Check if session is in valid local cache"""
        if session_id not in self._cache:
            return False
        
        import time
        cache_time = self._cache_timestamps.get(session_id, 0)
        return (time.time() - cache_time) < self._cache_ttl


def is_redis_configured() -> bool:
    """Check if Redis session storage is configured."""
    return bool(os.environ.get('PROXY_REDIS_URL'))


def create_redis_handler() -> RedisSessionIdHandler | None:
    """Create Redis session handler if configured."""
    redis_url = os.environ.get('PROXY_REDIS_URL')
    if not redis_url:
        return None
        
    redis_password = os.environ.get('PROXY_REDIS_PASSWORD')
    return RedisSessionIdHandler(redis_url, redis_password)