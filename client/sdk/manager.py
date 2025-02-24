"""Global manager for Authed SDK."""

from typing import Optional
import logging
from .config import AuthedConfig
from .auth import AgentAuth

# Set up logging
logger = logging.getLogger(__name__)

class Authed:
    """Global manager for Authed SDK."""
    
    _instance = None
    _auth: Optional[AgentAuth] = None
    
    def __init__(self):
        raise RuntimeError("Use initialize() or get_instance()")
    
    @classmethod
    def initialize(
        cls,
        registry_url: str,
        agent_id: Optional[str] = None,
        agent_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
    ) -> 'Authed':
        """Initialize the SDK with configuration."""
        logger.debug("Authed.initialize called")
        logger.debug(f"Current instance: {cls._instance}")
        logger.debug(f"Registry URL: {registry_url}")
        logger.debug(f"Agent ID: {agent_id}")
        logger.debug(f"Private key present: {bool(private_key)}")
        logger.debug(f"Public key present: {bool(public_key)}")
        
        if cls._instance is None:
            logger.debug("Creating new Authed instance")
            cls._instance = object.__new__(cls)
            cls._auth = AgentAuth(
                registry_url=registry_url,
                agent_id=agent_id,
                agent_secret=agent_secret,
                private_key=private_key,
                public_key=public_key
            )
            logger.debug("Authed instance created and initialized")
        else:
            logger.debug("Returning existing Authed instance")
            
        return cls._instance
    
    @classmethod
    def from_env(cls) -> 'Authed':
        """Initialize from environment variables."""
        logger.debug("Authed.from_env called")
        config = AuthedConfig.from_env()
        if not config.registry_url:
            raise ValueError("AUTHED_REGISTRY_URL environment variable is required")
            
        return cls.initialize(
            registry_url=config.registry_url,
            agent_id=config.agent_id,
            agent_secret=config.agent_secret,
            private_key=config.private_key,
            public_key=config.public_key
        )
    
    @classmethod
    def get_instance(cls) -> 'Authed':
        """Get the initialized SDK instance."""
        logger.debug("Authed.get_instance called")
        if cls._instance is None:
            logger.error("SDK not initialized")
            raise RuntimeError(
                "SDK not initialized. Call initialize() or from_env() first"
            )
        logger.debug("Returning existing Authed instance")
        return cls._instance
    
    @property
    def auth(self) -> AgentAuth:
        """Get the auth handler."""
        return self._auth 