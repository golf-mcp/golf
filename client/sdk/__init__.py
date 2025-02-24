"""
Authed SDK - A client library for interacting with the Authed service.
"""

from .manager import Authed
from .decorators.outgoing.httpx import protect_httpx
from .decorators.outgoing.requests import protect_requests
from .decorators.incoming.fastapi import verify_fastapi
from .models import (
    Agent,
    AgentPermission,
    PermissionType,
    TokenRequest,
    InteractionToken
)
from .exceptions import (
    AgentAuthError,
    AuthenticationError,
    ValidationError,
    DPoPError,
    RegistryError
)
from .config import AuthedConfig

__version__ = "0.1.0"
__all__ = [
    # Main class
    "Authed",
    
    # Decorators
    "protect_requests",
    "protect_httpx",
    "verify_fastapi",
    
    # Models
    "Agent",
    "AgentPermission",
    "PermissionType",
    "TokenRequest",
    "InteractionToken",
    
    # Exceptions
    "AgentAuthError",
    "AuthenticationError",
    "ValidationError",
    "DPoPError",
    "RegistryError",
    
    # Configuration
    "AuthedConfig"
] 