"""Decorator for protecting outgoing requests using the httpx library."""

from functools import wraps
import httpx
import logging
from ...manager import Authed

# Set up logging
logger = logging.getLogger(__name__)

def protect_httpx():
    """Decorator to protect httpx requests with agent authentication."""
    logger.debug("protect_httpx decorator called")
    
    # Get auth instance
    manager = Authed.get_instance()
    logger.debug(f"Got Authed instance: {manager}")
    auth = manager.auth
    logger.debug(f"Got auth handler: {auth}")
    
    # Create a protected client class
    class ProtectedAsyncClient(httpx.AsyncClient):
        async def get(self, url, **kwargs):
            logger.debug(f"Protected GET request to: {url}")
            headers = kwargs.get('headers', {})
            target_agent_id = headers.get('target-agent-id')
            
            if not target_agent_id:
                raise ValueError("target-agent-id header is required")
            
            logger.debug(f"Getting protected headers for target: {target_agent_id}")
            try:
                protected_headers = await auth.protect_request(
                    "GET",
                    url,
                    target_agent_id,
                    headers
                )
                logger.debug(f"Got protected headers: {protected_headers}")
                
                # Ensure we have authorization and dpop headers
                if 'authorization' not in protected_headers or 'dpop' not in protected_headers:
                    raise ValueError("Missing required auth headers after protection")
                    
                kwargs['headers'] = protected_headers
                logger.debug("Making request with protected headers")
                return await super().get(url, **kwargs)
                
            except Exception as e:
                logger.error(f"Error protecting request: {str(e)}", exc_info=True)
                raise
    
    def decorator(func):
        logger.debug(f"Decorating function: {func.__name__}")
        
        @wraps(func)
        async def wrapper(*args, **kwargs):
            logger.debug(f"Wrapper called for {func.__name__}")
            
            # Store original client class
            original_client = httpx.AsyncClient
            
            # Replace with our protected version
            httpx.AsyncClient = ProtectedAsyncClient
            
            try:
                # Call the original function
                return await func(*args, **kwargs)
            finally:
                # Restore original client
                httpx.AsyncClient = original_client
        
        return wrapper
    return decorator