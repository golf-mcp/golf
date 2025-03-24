from typing import Dict, Optional
import logging
import base64
from authed.sdk import Authed

logger = logging.getLogger(__name__)

class AuthedMCPHeaders:
    """Utility class to generate Authed authentication headers for MCP connections."""
    
    def __init__(
        self,
        authed: Authed,
        debug: bool = False
    ):
        """Initialize the header generator.
        
        Args:
            authed: Initialized Authed SDK instance
            debug: Enable debug logging
        """
        self.authed = authed
        self.debug = debug
    
    async def create_auth_headers(
        self,
        url: str,
        method: str,
        target_agent_id: Optional[str] = None,
        fallback: bool = True
    ) -> Dict[str, str]:
        """Create authentication headers for the request.
        
        Args:
            url: The URL of the request
            method: HTTP method
            target_agent_id: Agent ID of the target server
            fallback: Whether to fall back to basic auth if Authed auth fails
            
        Returns:
            Dict[str, str]: Headers to include in the request
        """
        headers = {
            'User-Agent': 'AuthedMCPClient/1.0'
        }
        
        # First try Authed auth if target_agent_id is specified
        if target_agent_id:
            if self.debug:
                logger.debug(f"Creating Authed authentication for target: {target_agent_id}")
            
            try:
                # Get auth handler from Authed SDK
                auth_handler = self.authed.auth
                
                # Create authentication headers
                auth_headers = await auth_handler.protect_request(
                    method=method,
                    url=url,
                    target_agent_id=target_agent_id
                )
                
                # Add the auth headers to our headers dict
                if auth_headers:
                    headers.update(auth_headers)
                    if self.debug:
                        logger.debug(f"Added Authed authentication headers: {list(auth_headers.keys())}")
                    return headers
                else:
                    logger.warning("No authentication headers returned by Authed SDK")
            except Exception as e:
                if self.debug:
                    logger.debug(f"Error creating Authed authentication: {str(e)}")
                # If fallback is not enabled, re-raise the exception
                if not fallback:
                    raise
        
        # Fallback to basic auth if Authed auth failed or not configured
        if fallback:
            if self.debug:
                logger.debug("Using fallback Basic authentication")
            
            auth_credentials = f"{self.authed.agent_id}:{self.authed.agent_secret}"
            encoded_credentials = base64.b64encode(auth_credentials.encode()).decode('utf-8')
            headers['Authorization'] = f"Basic {encoded_credentials}"
        
        return headers

# Helper functions
async def get_auth_headers(
    authed: Authed,
    url: str,
    method: str,
    target_agent_id: Optional[str] = None,
    fallback: bool = True,
    debug: bool = False
) -> Dict[str, str]:
    """Create Authed authentication headers for MCP connections.
    
    Args:
        authed: Initialized Authed SDK instance
        url: The URL of the request
        method: HTTP method
        target_agent_id: Agent ID of the target server
        fallback: Whether to fall back to basic auth if Authed auth fails
        debug: Enable debug logging
        
    Returns:
        Dict[str, str]: Headers to include in the request
    """
    header_generator = AuthedMCPHeaders(authed, debug)
    return await header_generator.create_auth_headers(
        url=url,
        method=method,
        target_agent_id=target_agent_id,
        fallback=fallback
    )
