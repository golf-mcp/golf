"""Tests for Redis session object storage"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from golf.session.store import RedisSessionStorage, RedisSessionIdHandler


class MockSessionTransport:
    """Mock session transport object for testing"""
    def __init__(self, session_id: str):
        self.mcp_session_id = session_id
        self.data = f"session_data_{session_id}"


class ComplexSessionTransport:
    """Mock complex session transport object for testing serialization"""
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.nested_data = {"key": "value", "list": [1, 2, 3]}
        self.metadata = {"created": "2024-01-01", "active": True}


class TestRedisSessionStorage:
    @pytest.fixture
    def redis_handler(self):
        handler = RedisSessionIdHandler("redis://localhost:6379")
        handler._redis = MagicMock()
        handler._initialized = True
        return handler
    
    @pytest.fixture  
    def storage(self, redis_handler):
        return RedisSessionStorage(redis_handler)
    
    def test_contains_check_cache_first(self, storage):
        """Test __contains__ checks local cache before Redis"""
        # Add to cache
        mock_transport = MockSessionTransport("test-session")
        storage._cache["test-session"] = mock_transport
        import time
        storage._cache_timestamps["test-session"] = time.time()
        
        assert "test-session" in storage
        
    def test_contains_check_redis_when_not_cached(self, storage):
        """Test __contains__ checks Redis when not in cache"""
        storage.redis._redis.exists = AsyncMock(return_value=1)
        
        result = "test-session" in storage
        assert result is True
        
    def test_getitem_from_cache(self, storage):
        """Test __getitem__ retrieves from cache when available"""
        mock_transport = MockSessionTransport("cached-session")
        storage._cache["cached-session"] = mock_transport
        import time
        storage._cache_timestamps["cached-session"] = time.time()
        
        result = storage["cached-session"]
        assert result == mock_transport
        
    def test_getitem_from_redis(self, storage):
        """Test __getitem__ retrieves from Redis when not cached"""
        mock_transport = MockSessionTransport("redis-session")
        import pickle
        serialized = pickle.dumps(mock_transport).decode('latin1')
        
        storage.redis._redis.get = AsyncMock(return_value=serialized)
        
        result = storage["redis-session"]
        assert result.mcp_session_id == "redis-session"
        assert result.data == "session_data_redis-session"
        
    def test_setitem_stores_in_cache_and_redis(self, storage):
        """Test __setitem__ stores in both cache and Redis"""
        mock_transport = MockSessionTransport("new-session")
        storage.redis._redis.setex = AsyncMock()
        
        storage["new-session"] = mock_transport
        
        # Check cache
        assert "new-session" in storage._cache
        assert storage._cache["new-session"] == mock_transport
        
        # Check Redis call
        storage.redis._redis.setex.assert_called_once()
        
    def test_delitem_removes_from_cache_and_redis(self, storage):
        """Test __delitem__ removes from both cache and Redis"""
        # Add to cache first
        storage._cache["to-delete"] = MockSessionTransport("to-delete")
        storage.redis._redis.delete = AsyncMock()
        
        del storage["to-delete"]
        
        # Check cache removal
        assert "to-delete" not in storage._cache
        
        # Check Redis call
        storage.redis._redis.delete.assert_called_once_with("golf:session_obj:to-delete")
        
    def test_graceful_degradation_redis_failure(self, storage):
        """Test graceful degradation when Redis operations fail"""
        storage.redis._redis.get = AsyncMock(side_effect=Exception("Redis error"))
        
        # Should raise KeyError (not Redis exception)
        with pytest.raises(KeyError):
            _ = storage["nonexistent-session"]
            
    def test_dictionary_interface_compatibility(self, storage):
        """Test that storage behaves like a dictionary"""
        mock_transport = MockSessionTransport("dict-test")
        storage.redis._redis.setex = AsyncMock()
        
        # Test dict-like operations
        storage["dict-test"] = mock_transport
        assert storage.get("dict-test") == mock_transport
        assert storage.get("nonexistent", "default") == "default"
        
    def test_cache_ttl_expiration(self, storage):
        """Test that cache entries expire after TTL"""
        mock_transport = MockSessionTransport("ttl-test")
        
        # Add to cache with old timestamp
        storage._cache["ttl-test"] = mock_transport
        import time
        storage._cache_timestamps["ttl-test"] = time.time() - 400  # Older than 300s TTL
        
        # Should not be considered cached
        assert not storage._is_cached("ttl-test")
        
    def test_keys_returns_combined_cache_and_redis_keys(self, storage):
        """Test keys() method combines cache and Redis keys"""
        # Add to cache
        storage._cache["cache-key"] = MockSessionTransport("cache-key")
        
        # Mock Redis keys
        storage.redis._redis.keys = AsyncMock(return_value=["golf:session_obj:redis-key"])
        
        keys = storage.keys()
        assert "cache-key" in keys
        assert "redis-key" in keys
        
    def test_no_redis_fallback_behavior(self):
        """Test behavior when Redis is not available"""
        # Create handler without Redis connection
        handler = RedisSessionIdHandler("redis://localhost:6379")
        handler._redis = None
        handler._initialized = True
        
        storage = RedisSessionStorage(handler)
        mock_transport = MockSessionTransport("no-redis")
        
        # Should work with cache only
        storage["no-redis"] = mock_transport
        assert storage["no-redis"] == mock_transport
        assert "no-redis" in storage
        
        # Should not check Redis
        assert not ("nonexistent" in storage)
        
    def test_serialization_deserialization_roundtrip(self, storage):
        """Test that complex objects can be serialized and deserialized"""
        complex_obj = ComplexSessionTransport("complex-123")
        
        # Test serialization/deserialization directly
        import pickle
        serialized = pickle.dumps(complex_obj).decode('latin1')
        deserialized = pickle.loads(serialized.encode('latin1'))
        
        # Verify roundtrip works
        assert deserialized.session_id == "complex-123"
        assert deserialized.nested_data == {"key": "value", "list": [1, 2, 3]}
        assert deserialized.metadata == {"created": "2024-01-01", "active": True}
        
        # Test with storage - mock Redis to return our serialized data
        storage.redis._redis.get = AsyncMock(return_value=serialized)
        
        # Clear cache to force Redis lookup
        storage._cache.clear()
        
        retrieved = storage["complex-123"]
        assert retrieved.session_id == "complex-123"
        assert retrieved.nested_data == {"key": "value", "list": [1, 2, 3]}
        assert retrieved.metadata == {"created": "2024-01-01", "active": True}