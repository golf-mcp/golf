"""Decorator for verifying incoming FastAPI requests."""

from functools import wraps
from typing import Callable
import logging
from fastapi import Request, HTTPException
from ...manager import Authed

# Set up logging
logger = logging.getLogger(__name__)

def verify_fastapi(required: bool = True):
    """Decorator to verify agent authentication on FastAPI endpoints.
    
    Args:
        required: Whether authentication is required (default: True)
    """
    logger.debug("verify_fastapi decorator called")
    logger.debug(f"Authentication required: {required}")
    
    # Get auth instance
    manager = Authed.get_instance()
    logger.debug(f"Got Authed instance: {manager}")
    auth = manager.auth
    logger.debug(f"Got auth handler: {auth}")
    logger.debug(f"Auth handler registry URL: {auth.registry_url}")
    
    def decorator(func: Callable) -> Callable:
        logger.debug(f"Decorating function: {func.__name__}")
        
        @wraps(func)
        async def wrapper(*args, request: Request, **kwargs):
            logger.debug(f"Wrapper called for {func.__name__}")
            logger.debug(f"Request method: {request.method}")
            logger.debug(f"Request URL: {request.url}")
            logger.debug(f"Request headers: {dict(request.headers)}")
            
            try:
                # Verify the request
                logger.debug("Verifying request...")
                is_valid = await auth.verify_request(
                    request.method,
                    str(request.url),
                    dict(request.headers)
                )
                logger.debug(f"Request verification result: {is_valid}")
                
                if not is_valid and required:
                    logger.error("Request verification failed and auth is required")
                    raise HTTPException(
                        status_code=401,
                        detail="Invalid or missing agent authentication"
                    )
                
                # Add auth info to request state
                request.state.authenticated = is_valid
                logger.debug(f"Added authentication state: {is_valid}")
                
                logger.debug(f"Calling original function: {func.__name__}")
                return await func(*args, request=request, **kwargs)
                
            except Exception as e:
                logger.error(f"Error in verify_fastapi wrapper: {str(e)}", exc_info=True)
                raise
                
        return wrapper
    return decorator