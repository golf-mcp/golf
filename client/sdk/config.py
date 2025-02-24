"""Configuration for Authed SDK."""

from typing import Optional
from pydantic import BaseModel

class AuthedConfig(BaseModel):
    """Configuration for Authed SDK."""
    registry_url: str
    
    # For outgoing requests (agent mode)
    agent_id: Optional[str] = None
    agent_secret: Optional[str] = None
    private_key: Optional[str] = None
    
    # For incoming requests (verification mode)
    public_key: Optional[str] = None
    
    class Config:
        env_prefix = "AUTHED_"
        
    @classmethod
    def from_env(cls) -> "AuthedConfig":
        """Create config from environment variables."""
        import os
        
        return cls(
            registry_url=os.getenv("AUTHED_REGISTRY_URL", ""),
            agent_id=os.getenv("AUTHED_AGENT_ID"),
            agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
            private_key=os.getenv("AUTHED_PRIVATE_KEY"),
            public_key=os.getenv("AUTHED_PUBLIC_KEY")
        ) 