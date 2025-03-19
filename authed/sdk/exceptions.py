"""Custom exceptions for the Agent Auth SDK."""

class AgentAuthError(Exception):
    """Base exception for all Agent Auth SDK errors."""
    pass

class AuthenticationError(AgentAuthError):
    """Raised when authentication fails."""
    pass

class ValidationError(AgentAuthError):
    """Raised when request validation fails."""
    pass

class RegistryError(AgentAuthError):
    """Raised when the registry service returns an error."""
    def __init__(self, status_code: int, detail: str):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Registry error {status_code}: {detail}")

class DPoPError(AgentAuthError):
    """Raised when DPoP operations fail."""
    pass

# Channel-specific exceptions
class ChannelError(AgentAuthError):
    """Base exception for all channel-related errors."""
    pass

class ConnectionError(ChannelError):
    """Raised when connection operations fail."""
    pass

class MessageError(ChannelError):
    """Raised when message operations fail."""
    pass

class ProtocolError(ChannelError):
    """Raised when protocol violations occur."""
    pass 