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