"""Tests for horizontal scaling with Redis session persistence"""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from golf.session.store import RedisSessionStorage, create_redis_handler


@pytest.mark.integration
class TestHorizontalScaling:
    """Integration tests requiring actual Redis instance"""
    
    @pytest.fixture
    def redis_handler(self):
        """Create Redis handler with test Redis instance"""
        return create_redis_handler()
    
    @pytest.mark.asyncio
    async def test_session_sharing_across_instances(self, redis_handler):
        """Test that multiple storage instances can share sessions"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        # Create two storage instances (simulating different server instances)
        storage1 = RedisSessionStorage(redis_handler)
        storage2 = RedisSessionStorage(redis_handler)
        
        # Create a mock session object
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.data = f"data_for_{session_id}"
        
        session = MockSession("shared-session-123")
        
        # Store in first instance
        storage1["shared-session-123"] = session
        
        # Retrieve from second instance
        retrieved_session = storage2["shared-session-123"]
        
        assert retrieved_session.mcp_session_id == "shared-session-123"
        assert retrieved_session.data == "data_for_shared-session-123"
        
    @pytest.mark.asyncio
    async def test_session_persistence_across_restarts(self, redis_handler):
        """Test that sessions persist when storage instances are recreated"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        # Create initial storage and store a session
        storage1 = RedisSessionStorage(redis_handler)
        
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.persistent_data = f"persistent_{session_id}"
        
        session = MockSession("persistent-session-456")
        storage1["persistent-session-456"] = session
        
        # Simulate server restart by creating new storage instance
        storage2 = RedisSessionStorage(redis_handler)
        
        # Verify session persists
        retrieved_session = storage2["persistent-session-456"]
        assert retrieved_session.mcp_session_id == "persistent-session-456"
        assert retrieved_session.persistent_data == "persistent_persistent-session-456"
        
    @pytest.mark.asyncio
    async def test_multiple_sessions_across_instances(self, redis_handler):
        """Test handling of multiple sessions across different storage instances"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        # Create multiple storage instances
        storage1 = RedisSessionStorage(redis_handler)
        storage2 = RedisSessionStorage(redis_handler)
        storage3 = RedisSessionStorage(redis_handler)
        
        class MockSession:
            def __init__(self, session_id, server_id):
                self.mcp_session_id = session_id
                self.server_id = server_id
                self.created_time = f"time_{session_id}"
        
        # Create sessions on different instances
        session1 = MockSession("multi-session-1", "server-1")
        session2 = MockSession("multi-session-2", "server-2")  
        session3 = MockSession("multi-session-3", "server-3")
        
        storage1["multi-session-1"] = session1
        storage2["multi-session-2"] = session2
        storage3["multi-session-3"] = session3
        
        # Verify each storage instance can access all sessions
        retrieved1_from_2 = storage2["multi-session-1"]
        retrieved2_from_3 = storage3["multi-session-2"]
        retrieved3_from_1 = storage1["multi-session-3"]
        
        assert retrieved1_from_2.mcp_session_id == "multi-session-1"
        assert retrieved1_from_2.server_id == "server-1"
        
        assert retrieved2_from_3.mcp_session_id == "multi-session-2"
        assert retrieved2_from_3.server_id == "server-2"
        
        assert retrieved3_from_1.mcp_session_id == "multi-session-3"
        assert retrieved3_from_1.server_id == "server-3"
        
    @pytest.mark.asyncio
    async def test_session_deletion_across_instances(self, redis_handler):
        """Test that session deletion is visible across all instances"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        storage1 = RedisSessionStorage(redis_handler)
        storage2 = RedisSessionStorage(redis_handler)
        
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.data = f"deletable_{session_id}"
        
        session = MockSession("delete-test-789")
        
        # Store session in first instance
        storage1["delete-test-789"] = session
        
        # Verify it exists in second instance
        assert "delete-test-789" in storage2
        retrieved = storage2["delete-test-789"]
        assert retrieved.data == "deletable_delete-test-789"
        
        # Delete from first instance
        del storage1["delete-test-789"]
        
        # Verify it's gone from second instance
        assert "delete-test-789" not in storage2
        with pytest.raises(KeyError):
            _ = storage2["delete-test-789"]
            
    @pytest.mark.asyncio
    async def test_cache_independence_across_instances(self, redis_handler):
        """Test that local caches are independent but Redis state is shared"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        storage1 = RedisSessionStorage(redis_handler)
        storage2 = RedisSessionStorage(redis_handler)
        
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.data = f"cache_test_{session_id}"
        
        session = MockSession("cache-independence-test")
        
        # Store in first instance (will be in its cache)
        storage1["cache-independence-test"] = session
        
        # Verify it's in first instance's cache
        assert "cache-independence-test" in storage1._cache
        
        # Verify it's NOT in second instance's cache initially
        assert "cache-independence-test" not in storage2._cache
        
        # But second instance can still retrieve it (from Redis)
        retrieved = storage2["cache-independence-test"]
        assert retrieved.data == "cache_test_cache-independence-test"
        
        # Now it should be in second instance's cache too
        assert "cache-independence-test" in storage2._cache
        
    @pytest.mark.asyncio
    async def test_concurrent_access_to_same_session(self, redis_handler):
        """Test concurrent access to the same session from different instances"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        storage1 = RedisSessionStorage(redis_handler)
        storage2 = RedisSessionStorage(redis_handler)
        
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.access_count = 0
                
            def increment_access(self):
                self.access_count += 1
        
        session = MockSession("concurrent-test")
        storage1["concurrent-test"] = session
        
        # Simulate concurrent access
        async def access_session(storage_instance, instance_name):
            retrieved = storage_instance["concurrent-test"]
            retrieved.increment_access()
            # Note: This test shows the limitation that modifications to objects
            # aren't automatically synced back to Redis - that would require
            # explicit re-storage
            return retrieved.mcp_session_id
        
        # Run concurrent accesses
        results = await asyncio.gather(
            access_session(storage1, "storage1"),
            access_session(storage2, "storage2")
        )
        
        assert all(result == "concurrent-test" for result in results)
        
    def test_graceful_degradation_during_redis_failure(self):
        """Test graceful behavior when Redis connection fails during operation"""
        # Create handler with invalid Redis URL
        from golf.session.store import RedisSessionIdHandler
        handler = RedisSessionIdHandler("redis://invalid-host:6379")
        handler._redis = None  # Simulate failed connection
        handler._initialized = True
        
        storage = RedisSessionStorage(handler)
        
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.data = f"fallback_{session_id}"
        
        session = MockSession("fallback-test")
        
        # Should still work with local cache
        storage["fallback-test"] = session
        assert storage["fallback-test"] == session
        assert "fallback-test" in storage
        
        # But operations that require Redis should handle gracefully
        assert storage.get("nonexistent", "default") == "default"
        
    @pytest.mark.asyncio  
    async def test_redis_reconnection_scenario(self, redis_handler):
        """Test behavior when Redis reconnects after being unavailable"""
        if not redis_handler:
            pytest.skip("Redis not configured for testing")
            
        await redis_handler.initialize()
        if not redis_handler._redis:
            pytest.skip("Cannot connect to Redis")
            
        storage = RedisSessionStorage(redis_handler)
        
        class MockSession:
            def __init__(self, session_id):
                self.mcp_session_id = session_id
                self.reconnect_data = f"reconnect_{session_id}"
        
        # Store session while Redis is available
        session = MockSession("reconnect-test")
        storage["reconnect-test"] = session
        
        # Simulate Redis disconnection
        original_redis = storage.redis._redis
        storage.redis._redis = None
        
        # Operations should fall back to cache
        cached_session = storage["reconnect-test"]  # Should work from cache
        assert cached_session.reconnect_data == "reconnect_reconnect-test"
        
        # Restore Redis connection
        storage.redis._redis = original_redis
        
        # Should be able to access Redis again
        assert "reconnect-test" in storage
        redis_session = storage["reconnect-test"]
        assert redis_session.reconnect_data == "reconnect_reconnect-test"