from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any
import logging
import os

from golf.session.store import RedisSessionStorage, create_redis_handler, RedisSessionIdHandler

logger = logging.getLogger(__name__)


def _patch_streamable_http_session_manager(redis_handler: RedisSessionIdHandler) -> None:
    """Patch StreamableHTTPSessionManager.__init__ for instance-level Redis storage."""
    try:
        from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

        # Store original __init__ method
        original_init = StreamableHTTPSessionManager.__init__

        def custom_init(self, *args, **kwargs):
            # Call original initialization
            original_init(self, *args, **kwargs)
            # Set instance-level Redis storage
            self._server_instances = RedisSessionStorage(redis_handler)
            if os.environ.get("GOLF_DEBUG"):
                print(f"Set _server_instances to Redis storage for instance {id(self)}")

        # Apply the monkey-patch
        StreamableHTTPSessionManager.__init__ = custom_init
        print("StreamableHTTPSessionManager.__init__ patched for instance-level Redis persistence")

    except (ImportError, AttributeError) as e:
        print(f"Warning: Could not patch StreamableHTTPSessionManager.__init__: {e}")
        print("Session objects will use in-memory storage only")


@asynccontextmanager
async def redis_session_lifespan(mcp_instance: Any) -> AsyncGenerator[None, None]:
    """Redis session storage lifespan for initialization and cleanup."""

    print("Redis session lifespan starting...")
    redis_session_handler = None

    try:
        # Initialize Redis connection within event loop
        redis_session_handler = create_redis_handler()
        if redis_session_handler:
            print("Attempting Redis initialization...")
            connected = await redis_session_handler.initialize()
            if connected:
                print("Enhanced Redis session storage enabled")
                # Patch StreamableHTTPSessionManager for session object persistence
                _patch_streamable_http_session_manager(redis_session_handler)
            else:
                print("Warning: Redis connection failed, using default session storage")
        else:
            print("No Redis configuration found, using default session storage")

        # Apply Context.session_id patching (this part works and doesn't need event loop)
        _patch_context_session_id(redis_session_handler)

        # Server runs here
        yield

    finally:
        # Cleanup Redis connection
        if redis_session_handler and redis_session_handler._redis:
            print("Closing Redis connection...")
            await redis_session_handler.close()
            print("Redis connection closed")


def _patch_context_session_id(redis_session_handler: Any) -> None:
    """Apply Context.session_id patching for Redis-backed session ID persistence."""
    if not redis_session_handler:
        return

    print("Patching Context.session_id for Redis persistence...")
    import fastmcp.server.context
    import asyncio
    import os

    # Get the current property to access its getter function
    original_property = fastmcp.server.context.Context.session_id
    original_session_id_func = original_property.fget if hasattr(original_property, "fget") else None

    def redis_session_id(self: Any) -> str:
        # Try to get session ID from Redis first
        if redis_session_handler and redis_session_handler._redis:
            try:
                # Use request hash as context key for session persistence
                context_key = str(hash(str(self)))
                if os.environ.get("GOLF_DEBUG"):
                    print(f"Looking up session ID for context_key: {context_key}")
                session_id = asyncio.run(redis_session_handler.get_session_id(context_key))
                if session_id:
                    if os.environ.get("GOLF_DEBUG"):
                        print(f"Found existing session ID: {session_id}")
                    return str(session_id)
                # Generate new session ID and store in Redis
                new_session_id = asyncio.run(redis_session_handler.generate_and_store_session_id(context_key))
                if os.environ.get("GOLF_DEBUG"):
                    print(f"Generated new session ID: {new_session_id}")
                return str(new_session_id)
            except Exception as e:
                if os.environ.get("GOLF_DEBUG"):
                    print(f"Redis session ID lookup failed: {e}, falling back to original behavior")
                pass  # Fall back to original behavior
        # Fall back to original FastMCP session ID behavior
        if original_session_id_func:
            fallback_id = original_session_id_func(self)
        else:
            # Fallback if we can't access the original function
            from uuid import uuid4

            fallback_id = str(uuid4())
        if os.environ.get("GOLF_DEBUG"):
            print(f"Using fallback session ID: {fallback_id}")
        return str(fallback_id)

    # Apply the Context.session_id patch
    setattr(fastmcp.server.context.Context, "session_id", property(redis_session_id))
    print("Context.session_id patched successfully")


@asynccontextmanager
async def combined_lifespan(mcp_instance: Any) -> AsyncGenerator[None, None]:
    """Combined lifespan for both telemetry and Redis session storage."""

    # Initialize telemetry
    from golf.telemetry.instrumentation import init_telemetry

    provider = None

    print("Combined lifespan starting (telemetry + Redis)...")

    try:
        provider = init_telemetry(service_name=mcp_instance.name)

        # Initialize Redis
        redis_session_handler = None
        redis_session_handler = create_redis_handler()
        if redis_session_handler:
            print("Attempting Redis initialization...")
            connected = await redis_session_handler.initialize()
            if connected:
                print("Enhanced Redis session storage enabled")

                # Patch StreamableHTTPSessionManager for session object persistence
                _patch_streamable_http_session_manager(redis_session_handler)
            else:
                print("Warning: Redis connection failed, using default session storage")
        else:
            print("No Redis configuration found, using default session storage")

        # Apply Context.session_id patching
        _patch_context_session_id(redis_session_handler)

        # Add telemetry middleware if possible
        if provider and hasattr(mcp_instance, "app"):
            app = getattr(mcp_instance, "app", None)
            if app and hasattr(app, "add_middleware"):
                try:
                    from golf.telemetry.instrumentation import SessionTracingMiddleware

                    app.add_middleware(SessionTracingMiddleware)
                    print("Telemetry middleware added")
                except ImportError:
                    print("Warning: Could not import telemetry middleware")

        # Server runs here
        yield

    finally:
        # Cleanup Redis
        if redis_session_handler and redis_session_handler._redis:
            print("Closing Redis connection...")
            await redis_session_handler.close()
            print("Redis connection closed")

        # Cleanup telemetry
        if provider and hasattr(provider, "shutdown"):
            try:
                provider.force_flush()
                provider.shutdown()
                print("Telemetry provider shutdown")
            except Exception as e:
                print(f"Warning: Telemetry shutdown error: {e}")
