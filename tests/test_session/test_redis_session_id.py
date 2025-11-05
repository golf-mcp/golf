import pytest
from unittest.mock import AsyncMock, patch
from golf.session.redis_session_id import RedisSessionIdHandler, is_redis_configured, create_redis_handler


class TestRedisSessionIdHandler:
    @pytest.fixture
    def handler(self):
        return RedisSessionIdHandler("redis://localhost:6379")
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, handler):
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis.return_value.ping = AsyncMock()
            result = await handler.initialize()
            assert result is True
            assert handler._initialized is True
            assert handler._redis is not None
    
    @pytest.mark.asyncio
    async def test_initialize_failure(self, handler):
        with patch('redis.asyncio.from_url') as mock_redis:
            mock_redis.return_value.ping = AsyncMock(side_effect=Exception("Connection failed"))
            result = await handler.initialize()
            assert result is False
            assert handler._initialized is True
            assert handler._redis is None
    
    @pytest.mark.asyncio
    async def test_initialize_already_initialized(self, handler):
        handler._initialized = True
        handler._redis = "mock_redis"
        
        with patch('redis.asyncio.from_url') as mock_redis:
            result = await handler.initialize()
            mock_redis.assert_not_called()
            assert result is True
    
    @pytest.mark.asyncio  
    async def test_get_session_id_success(self, handler):
        with patch.object(handler, '_redis') as mock_redis:
            mock_redis.get = AsyncMock(return_value="test-session-123")
            result = await handler.get_session_id("context-key")
            assert result == "test-session-123"
            mock_redis.get.assert_called_once_with("golf:session_id:context-key")
    
    @pytest.mark.asyncio
    async def test_get_session_id_no_redis(self, handler):
        handler._redis = None
        result = await handler.get_session_id("context-key")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_session_id_redis_error(self, handler):
        with patch.object(handler, '_redis') as mock_redis:
            mock_redis.get = AsyncMock(side_effect=Exception("Redis error"))
            result = await handler.get_session_id("context-key")
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_session_id_none_result(self, handler):
        with patch.object(handler, '_redis') as mock_redis:
            mock_redis.get = AsyncMock(return_value=None)
            result = await handler.get_session_id("context-key")
            assert result is None
            
    @pytest.mark.asyncio
    async def test_store_session_id_success(self, handler):
        with patch.object(handler, '_redis') as mock_redis:
            mock_redis.setex = AsyncMock()
            await handler.store_session_id("context-key", "session-123")
            mock_redis.setex.assert_called_once_with("golf:session_id:context-key", 3600, "session-123")
    
    @pytest.mark.asyncio
    async def test_store_session_id_no_redis(self, handler):
        handler._redis = None
        await handler.store_session_id("context-key", "session-123")
        # Should not raise any exception
    
    @pytest.mark.asyncio
    async def test_store_session_id_redis_error(self, handler):
        with patch.object(handler, '_redis') as mock_redis:
            mock_redis.setex = AsyncMock(side_effect=Exception("Redis error"))
            await handler.store_session_id("context-key", "session-123")
            # Should not raise any exception due to graceful degradation
    
    @pytest.mark.asyncio
    async def test_generate_and_store_session_id(self, handler):
        with patch.object(handler, 'store_session_id') as mock_store:
            with patch('golf.session.redis_session_id.uuid4', return_value="mock-uuid"):
                result = await handler.generate_and_store_session_id("context-key")
                assert result == "mock-uuid"
                mock_store.assert_called_once_with("context-key", "mock-uuid")


class TestUtilityFunctions:
    def test_is_redis_configured_true(self):
        with patch('os.environ.get', return_value='redis://localhost:6379'):
            assert is_redis_configured() is True
    
    def test_is_redis_configured_false(self):
        with patch('os.environ.get', return_value=None):
            assert is_redis_configured() is False
    
    def test_is_redis_configured_empty_string(self):
        with patch('os.environ.get', return_value=''):
            assert is_redis_configured() is False
    
    def test_create_redis_handler_configured(self):
        with patch('os.environ.get') as mock_get:
            mock_get.side_effect = lambda key: {
                'PROXY_REDIS_URL': 'redis://localhost:6379',
                'PROXY_REDIS_PASSWORD': 'secret'
            }.get(key)
            
            handler = create_redis_handler()
            assert handler is not None
            assert handler.redis_url == 'redis://localhost:6379'
            assert handler.redis_password == 'secret'
    
    def test_create_redis_handler_not_configured(self):
        with patch('os.environ.get', return_value=None):
            handler = create_redis_handler()
            assert handler is None
    
    def test_create_redis_handler_no_password(self):
        with patch('os.environ.get') as mock_get:
            mock_get.side_effect = lambda key: {
                'PROXY_REDIS_URL': 'redis://localhost:6379',
                'PROXY_REDIS_PASSWORD': None
            }.get(key)
            
            handler = create_redis_handler()
            assert handler is not None
            assert handler.redis_url == 'redis://localhost:6379'
            assert handler.redis_password is None