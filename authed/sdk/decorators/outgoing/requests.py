"""Decorator for protecting outgoing requests using the requests library."""

from functools import wraps
from typing import Optional, Callable
import requests
from ...manager import Authed

def protect_requests():
    """Decorator to protect requests with agent authentication."""
    auth = Authed.get_instance().auth
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get session from args or kwargs
            session = None
            if args and isinstance(args[0], requests.Session):
                session = args[0]
            elif 'session' in kwargs and isinstance(kwargs['session'], requests.Session):
                session = kwargs['session']
                
            if session:
                # Patch the session's request method
                original_request = session.request
                
                @wraps(original_request)
                def wrapped_request(method: str, url: str, headers: Optional[dict] = None, **request_kwargs):
                    protected_headers = auth.protect_request(method, url, headers)
                    request_kwargs['headers'] = protected_headers
                    return original_request(method, url, **request_kwargs)
                
                session.request = wrapped_request.__get__(session, type(session))
            
            return func(*args, **kwargs)
        return wrapper
    return decorator 