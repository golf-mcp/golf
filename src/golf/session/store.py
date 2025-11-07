"""Redis-backed session storage for Golf MCP servers"""

import os
import pickle
import asyncio
import logging
import concurrent.futures
from typing import Any
import redis.asyncio as redis
from uuid import uuid4

# Configure logging for Redis session storage
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def _run_async_safely(coro):
    """Run async coroutine safely, avoiding nested event loops."""
    try:
        # Check if we're already in an event loop
        loop = asyncio.get_running_loop()
        # We're in an event loop, need to run in thread
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()
    except RuntimeError:
        # No event loop running, safe to use asyncio.run
        return asyncio.run(coro)


class RedisSessionIdHandler:
    """Simple Redis handler for session ID persistence."""

    def __init__(self, redis_url: str, redis_password: str | None = None) -> None:
        self.redis_url = redis_url
        self.redis_password = redis_password
        self._redis: redis.Redis | None = None
        self._initialized = False

    async def initialize(self) -> bool:
        """Initialize Redis connection with graceful fallback."""
        logger.debug(f"RedisSessionIdHandler.initialize() called, already_initialized={self._initialized}")

        if self._initialized:
            result = self._redis is not None
            logger.debug(f"Already initialized, returning {result}")
            return result

        try:
            logger.debug(f"Attempting to connect to Redis at {self.redis_url}")
            self._redis = redis.from_url(self.redis_url, password=self.redis_password, decode_responses=True)
            await self._redis.ping()
            self._initialized = True
            logger.info(f"Successfully connected to Redis at {self.redis_url}")
            return True
        except Exception as e:
            logger.warning(f"Failed to connect to Redis at {self.redis_url}: {e}")
            self._redis = None
            self._initialized = True
            return False

    async def get_session_id(self, context_key: str) -> str | None:
        """Get session ID from Redis."""
        logger.debug(f"get_session_id called for context_key={context_key}")

        if not self._redis:
            logger.debug("No Redis connection available for get_session_id")
            return None

        try:
            redis_key = f"golf:session_id:{context_key}"
            result = await self._redis.get(redis_key)
            logger.debug(f"Redis get({redis_key}) returned: {result}")
            return result if result is not None else None
        except Exception as e:
            logger.warning(f"Error getting session ID for {context_key}: {e}")
            return None  # Graceful degradation

    async def store_session_id(self, context_key: str, session_id: str) -> None:
        """Store session ID in Redis with 1 hour TTL."""
        logger.debug(f"store_session_id called for context_key={context_key}, session_id={session_id}")

        if not self._redis:
            logger.debug("No Redis connection available for store_session_id")
            return

        try:
            redis_key = f"golf:session_id:{context_key}"
            await self._redis.setex(redis_key, 3600, session_id)
            logger.debug(f"Stored session ID {session_id} with key {redis_key} (TTL: 3600s)")
        except Exception as e:
            logger.warning(f"Error storing session ID for {context_key}: {e}")

    async def generate_and_store_session_id(self, context_key: str) -> str:
        """Generate new session ID and store it."""
        session_id = str(uuid4())
        logger.debug(f"Generated new session ID {session_id} for context_key={context_key}")
        await self.store_session_id(context_key, session_id)
        return session_id

    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        if self._redis:
            await self._redis.close()
            self._redis = None
        self._initialized = False
        logger.info("Redis connection closed")


class RedisSessionStorage:
    """Redis-backed dictionary replacement for _server_instances"""

    def __init__(self, redis_handler: RedisSessionIdHandler) -> None:
        self.redis = redis_handler
        self._cache: dict[str, Any] = {}  # Local cache for performance
        self._cache_ttl = 300  # 5 minutes local cache TTL
        self._cache_timestamps: dict[str, float] = {}
        logger.info(f"RedisSessionStorage initialized with TTL={self._cache_ttl}s")

    def __contains__(self, session_id: str) -> bool:
        """Check if session exists in cache or Redis"""
        logger.debug(f"__contains__ called for session_id={session_id}")

        # Check local cache first
        if self._is_cached(session_id):
            logger.debug(f"Session {session_id} found in local cache")
            return True

        # Check Redis
        if not self.redis._redis:
            logger.debug(f"No Redis connection available for __contains__ check of {session_id}")
            return False

        try:
            # Use _run_async_safely for sync interface compatibility
            redis_key = f"golf:session_obj:{session_id}"
            exists_coroutine = self.redis._redis.exists(redis_key)
            result = _run_async_safely(exists_coroutine)
            logger.debug(f"Redis exists({redis_key}) returned: {result}")
            return bool(result)
        except Exception as e:
            logger.warning(f"Error checking session existence in Redis for {session_id}: {e}")
            return False

    def __getitem__(self, session_id: str) -> Any:
        """Get session transport object from cache or Redis"""
        logger.debug(f"__getitem__ called for session_id={session_id}")

        # Try cache first
        if self._is_cached(session_id):
            logger.debug(f"Retrieved session {session_id} from local cache")
            return self._cache[session_id]

        # Try Redis
        if not self.redis._redis:
            logger.debug(f"No Redis connection available for __getitem__ of {session_id}")
            raise KeyError(session_id)

        try:
            # Retrieve serialized session from Redis
            redis_key = f"golf:session_obj:{session_id}"
            get_coroutine = self.redis._redis.get(redis_key)
            data = _run_async_safely(get_coroutine)
            logger.debug(f"Redis get({redis_key}) returned data length: {len(data) if data else 0}")

            if data is None:
                logger.debug(f"Session {session_id} not found in Redis")
                raise KeyError(session_id)

            # Deserialize session transport object
            session_transport = pickle.loads(data.encode("latin1"))
            logger.debug(f"Successfully deserialized session object for {session_id}")

            # Update local cache
            self._cache[session_id] = session_transport
            import time

            self._cache_timestamps[session_id] = time.time()
            logger.debug(f"Cached session {session_id} locally")

            return session_transport
        except Exception as e:
            if isinstance(e, KeyError):
                raise
            # For other errors, treat as missing
            logger.warning(f"Error retrieving session {session_id} from Redis: {e}")
            raise KeyError(session_id) from e

    def __setitem__(self, session_id: str, transport_obj: Any) -> None:
        """Store session transport object in cache and Redis"""
        logger.debug(f"__setitem__ called for session_id={session_id}")

        # Store in local cache
        self._cache[session_id] = transport_obj
        import time

        self._cache_timestamps[session_id] = time.time()
        logger.debug(f"Stored session {session_id} in local cache")

        # Store in Redis
        if self.redis._redis:
            try:
                # Serialize session transport object
                serialized = pickle.dumps(transport_obj).decode("latin1")
                logger.debug(f"Serialized session {session_id} to {len(serialized)} characters")

                # Store in Redis with TTL (1 hour)
                redis_key = f"golf:session_obj:{session_id}"
                setex_coroutine = self.redis._redis.setex(redis_key, 3600, serialized)
                _run_async_safely(setex_coroutine)
                logger.debug(f"Stored session {session_id} in Redis with key {redis_key} (TTL: 3600s)")
            except Exception as e:
                # Graceful degradation - keep in local cache only
                logger.warning(f"Error storing session {session_id} in Redis: {e}, keeping in local cache only")
        else:
            logger.debug(f"No Redis connection available for storing session {session_id}, using local cache only")

    def __delitem__(self, session_id: str) -> None:
        """Remove session from cache and Redis"""
        logger.debug(f"__delitem__ called for session_id={session_id}")

        # Remove from local cache
        was_in_cache = session_id in self._cache
        self._cache.pop(session_id, None)
        self._cache_timestamps.pop(session_id, None)
        if was_in_cache:
            logger.debug(f"Removed session {session_id} from local cache")

        # Remove from Redis
        if self.redis._redis:
            try:
                redis_key = f"golf:session_obj:{session_id}"
                delete_coroutine = self.redis._redis.delete(redis_key)
                result = _run_async_safely(delete_coroutine)
                logger.debug(f"Redis delete({redis_key}) returned: {result}")
            except Exception as e:
                logger.warning(f"Error deleting session {session_id} from Redis: {e}")
        else:
            logger.debug(f"No Redis connection available for deleting session {session_id}")

    def get(self, session_id: str, default: Any = None) -> Any:
        """Dict-compatible get method"""
        try:
            return self[session_id]
        except KeyError:
            return default

    def keys(self) -> set[str]:
        """Return all session IDs (for compatibility)"""
        logger.debug("keys() called")

        if not self.redis._redis:
            cache_keys = set(self._cache.keys())
            logger.debug(f"No Redis connection, returning {len(cache_keys)} cache keys")
            return cache_keys

        try:
            # Get all Redis keys matching our pattern
            keys_coroutine = self.redis._redis.keys("golf:session_obj:*")
            redis_keys = _run_async_safely(keys_coroutine)
            # Extract session IDs from Redis keys
            redis_session_ids = [key.replace("golf:session_obj:", "") for key in redis_keys]
            # Combine with local cache keys
            cache_keys = set(self._cache.keys())
            all_keys = set(redis_session_ids) | cache_keys
            logger.debug(
                f"Found {len(redis_session_ids)} Redis keys + {len(cache_keys)} cache keys = {len(all_keys)} total"
            )
            return all_keys
        except Exception as e:
            logger.warning(f"Error getting keys from Redis: {e}, returning cache keys only")
            cache_keys = set(self._cache.keys())
            return cache_keys

    def _is_cached(self, session_id: str) -> bool:
        """Check if session is in valid local cache"""
        if session_id not in self._cache:
            return False

        import time

        cache_time = self._cache_timestamps.get(session_id, 0)
        return (time.time() - cache_time) < self._cache_ttl

    # Async versions of sync methods for internal use
    async def async_contains(self, session_id: str) -> bool:
        """Async version of __contains__ for internal use."""
        logger.debug(f"async_contains called for session_id={session_id}")

        # Check local cache first
        if self._is_cached(session_id):
            logger.debug(f"Session {session_id} found in local cache")
            return True

        # Check Redis without asyncio.run()
        if not self.redis._redis:
            logger.debug(f"No Redis connection available for async_contains check of {session_id}")
            return False

        try:
            redis_key = f"golf:session_obj:{session_id}"
            result = await self.redis._redis.exists(redis_key)
            logger.debug(f"Redis exists({redis_key}) returned: {result}")
            return bool(result)
        except Exception as e:
            logger.warning(f"Error checking session existence in Redis for {session_id}: {e}")
            return False

    async def async_getitem(self, session_id: str) -> Any:
        """Async version of __getitem__ for internal use."""
        logger.debug(f"async_getitem called for session_id={session_id}")

        # Try cache first
        if self._is_cached(session_id):
            logger.debug(f"Retrieved session {session_id} from local cache")
            return self._cache[session_id]

        # Try Redis without asyncio.run()
        if not self.redis._redis:
            logger.debug(f"No Redis connection available for async_getitem of {session_id}")
            raise KeyError(session_id)

        try:
            # Retrieve serialized session from Redis
            redis_key = f"golf:session_obj:{session_id}"
            data = await self.redis._redis.get(redis_key)
            logger.debug(f"Redis get({redis_key}) returned data length: {len(data) if data else 0}")

            if data is None:
                logger.debug(f"Session {session_id} not found in Redis")
                raise KeyError(session_id)

            # Deserialize session transport object
            session_transport = pickle.loads(data.encode("latin1"))
            logger.debug(f"Successfully deserialized session object for {session_id}")

            # Update local cache
            self._cache[session_id] = session_transport
            import time
            self._cache_timestamps[session_id] = time.time()
            logger.debug(f"Cached session {session_id} locally")

            return session_transport
        except Exception as e:
            if isinstance(e, KeyError):
                raise
            # For other errors, treat as missing
            logger.warning(f"Error retrieving session {session_id} from Redis: {e}")
            raise KeyError(session_id) from e

    async def async_setitem(self, session_id: str, transport_obj: Any) -> None:
        """Async version of __setitem__ for internal use."""
        logger.debug(f"async_setitem called for session_id={session_id}")

        # Store in local cache
        self._cache[session_id] = transport_obj
        import time
        self._cache_timestamps[session_id] = time.time()
        logger.debug(f"Stored session {session_id} in local cache")

        # Store in Redis without asyncio.run()
        if self.redis._redis:
            try:
                # Serialize session transport object
                serialized = pickle.dumps(transport_obj).decode("latin1")
                logger.debug(f"Serialized session {session_id} to {len(serialized)} characters")

                # Store in Redis with TTL (1 hour)
                redis_key = f"golf:session_obj:{session_id}"
                await self.redis._redis.setex(redis_key, 3600, serialized)
                logger.debug(f"Stored session {session_id} in Redis with key {redis_key} (TTL: 3600s)")
            except Exception as e:
                # Graceful degradation - keep in local cache only
                logger.warning(f"Error storing session {session_id} in Redis: {e}, keeping in local cache only")
        else:
            logger.debug(f"No Redis connection available for storing session {session_id}, using local cache only")

    async def async_delitem(self, session_id: str) -> None:
        """Async version of __delitem__ for internal use."""
        logger.debug(f"async_delitem called for session_id={session_id}")

        # Remove from local cache
        was_in_cache = session_id in self._cache
        self._cache.pop(session_id, None)
        self._cache_timestamps.pop(session_id, None)
        if was_in_cache:
            logger.debug(f"Removed session {session_id} from local cache")

        # Remove from Redis without asyncio.run()
        if self.redis._redis:
            try:
                redis_key = f"golf:session_obj:{session_id}"
                result = await self.redis._redis.delete(redis_key)
                logger.debug(f"Redis delete({redis_key}) returned: {result}")
            except Exception as e:
                logger.warning(f"Error deleting session {session_id} from Redis: {e}")
        else:
            logger.debug(f"No Redis connection available for deleting session {session_id}")

    async def async_keys(self) -> set[str]:
        """Async version of keys() for internal use."""
        logger.debug("async_keys() called")

        if not self.redis._redis:
            cache_keys = set(self._cache.keys())
            logger.debug(f"No Redis connection, returning {len(cache_keys)} cache keys")
            return cache_keys

        try:
            # Get all Redis keys matching our pattern without asyncio.run()
            redis_keys = await self.redis._redis.keys("golf:session_obj:*")
            # Extract session IDs from Redis keys
            redis_session_ids = [key.replace("golf:session_obj:", "") for key in redis_keys]
            # Combine with local cache keys
            cache_keys = set(self._cache.keys())
            all_keys = set(redis_session_ids) | cache_keys
            logger.debug(
                f"Found {len(redis_session_ids)} Redis keys + {len(cache_keys)} cache keys = {len(all_keys)} total"
            )
            return all_keys
        except Exception as e:
            logger.warning(f"Error getting keys from Redis: {e}, returning cache keys only")
            cache_keys = set(self._cache.keys())
            return cache_keys


def is_redis_configured() -> bool:
    """Check if Redis session storage is configured."""
    return bool(os.environ.get("PROXY_REDIS_URL"))


def create_redis_handler() -> RedisSessionIdHandler | None:
    """Create Redis session handler if configured."""
    redis_url = os.environ.get("PROXY_REDIS_URL")
    if not redis_url:
        return None

    redis_password = os.environ.get("PROXY_REDIS_PASSWORD")
    return RedisSessionIdHandler(redis_url, redis_password)
