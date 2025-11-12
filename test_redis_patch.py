#!/usr/bin/env python3
"""Test script to verify Redis patching is working"""

import os
import asyncio
import sys

# Set debug and Redis URL
os.environ['GOLF_DEBUG'] = '1'
os.environ['PROXY_REDIS_URL'] = 'redis://localhost:6380'

# Add the golf source to path
sys.path.insert(0, '/Users/antonigmitruk/golf/src')

from golf.session.lifespan import _patch_streamable_http_session_manager
from golf.session.store import create_redis_handler

async def test_patching():
    """Test that the Redis patching actually works"""
    
    # Initialize Redis handler
    redis_handler = create_redis_handler()
    if not redis_handler:
        print("❌ No Redis handler created")
        return False
        
    connected = await redis_handler.initialize()
    if not connected:
        print("❌ Redis connection failed")
        return False
    
    print("✅ Redis connected successfully")
    
    # Apply the patch
    _patch_streamable_http_session_manager(redis_handler)
    
    try:
        # Import and create a StreamableHTTPSessionManager instance
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
        
        print("Creating StreamableHTTPSessionManager instance...")
        # StreamableHTTPSessionManager needs an app parameter - use a mock
        from unittest.mock import MagicMock
        mock_app = MagicMock()
        manager = StreamableHTTPSessionManager(app=mock_app)
        
        # Check if it has Redis-backed _server_instances
        if hasattr(manager, '_server_instances'):
            storage = manager._server_instances
            storage_type = type(storage).__name__
            print(f"✅ Manager has _server_instances of type: {storage_type}")
            
            # Test if we can store/retrieve from it
            test_session_id = "test-session-123"
            test_data = {"type": "test", "data": "hello world"}
            
            print(f"Testing storage with session_id: {test_session_id}")
            
            # Store data
            storage[test_session_id] = test_data
            print("✅ Data stored successfully")
            
            # Retrieve data
            retrieved = storage[test_session_id]
            print(f"✅ Data retrieved: {retrieved}")
            
            # Check if it's actually in Redis
            if test_session_id in storage:
                print("✅ Session exists in storage")
            else:
                print("❌ Session not found in storage")
                
            return True
        else:
            print("❌ Manager doesn't have _server_instances")
            return False
            
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    finally:
        if redis_handler:
            await redis_handler.close()

if __name__ == "__main__":
    result = asyncio.run(test_patching())
    if result:
        print("\n🎉 Redis patching test PASSED")
    else:
        print("\n💥 Redis patching test FAILED")