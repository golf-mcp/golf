"""Core authentication functionality for Agent Auth SDK."""

from typing import Optional, Dict
from uuid import UUID
import httpx
from urllib.parse import urlparse, parse_qs, urlencode
from .dpop import DPoPHandler
from .tokens import TokenManager
from ..exceptions import AuthenticationError, RegistryError
import logging

def normalize_url(url: str) -> str:
    """Normalize URL for comparison"""
    parsed = urlparse(url)
    # Sort query parameters
    if parsed.query:
        params = parse_qs(parsed.query)
        sorted_params = {k: sorted(v) for k, v in params.items()}
        query = urlencode(sorted_params, doseq=True)
    else:
        query = ""
    # Normalize port
    port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
    # Always use HTTPS for registry URLs
    scheme = "https" if "getauthed.dev" in parsed.netloc else parsed.scheme
    return f"{scheme}://{parsed.netloc}{port}{parsed.path}"

class AgentAuth:
    """Main authentication handler for Agent Auth."""
    
    def __init__(
        self,
        registry_url: str,
        agent_id: Optional[str] = None,
        agent_secret: Optional[str] = None,
        private_key: Optional[str] = None,
        public_key: Optional[str] = None
    ):
        """Initialize auth handler.
        
        Can be initialized in two modes:
        1. Outgoing requests (agent_id, agent_secret, private_key required)
        2. Incoming requests (public_key required)
        
        The keys should be pre-generated using the CLI tools and loaded from
        files or environment variables.
        
        Raises:
            ValueError: If the required credentials for either mode are missing
        """
        # Ensure HTTPS for registry URLs
        if "getauthed.dev" in registry_url and registry_url.startswith("http://"):
            registry_url = "https://" + registry_url[7:]
        self.registry_url = registry_url.rstrip('/')
        self._agent_id = agent_id
        self._agent_secret = agent_secret
        self._private_key = private_key
        self._public_key = public_key
        
        # Initialize handlers
        self._dpop = DPoPHandler()
        self._token_manager = TokenManager(registry_url)
        
        # Validate initialization mode
        if (agent_id or agent_secret or private_key) and not all([agent_id, agent_secret, private_key]):
            raise ValueError("For outgoing requests, all agent credentials are required")
            
    async def get_interaction_token(
        self,
        target_agent_id: UUID,
        registry_url: Optional[str] = None
    ) -> str:
        """Get or refresh interaction token for a specific target agent.
        
        Args:
            target_agent_id: The ID of the target agent to interact with
            registry_url: Optional override for registry URL (to match request scheme)
            
        Returns:
            str: The interaction token
            
        Raises:
            AuthenticationError: If agent credentials are missing or invalid
            RegistryError: If the registry service returns an error
        """
        logger = logging.getLogger(__name__)
        logger.debug(f"Getting interaction token for target agent: {target_agent_id}")
        
        if not self._agent_id or not self._agent_secret or not self._private_key:
            logger.error("Missing required credentials")
            logger.debug(f"agent_id present: {bool(self._agent_id)}")
            logger.debug(f"agent_secret present: {bool(self._agent_secret)}")
            logger.debug(f"private_key present: {bool(self._private_key)}")
            raise AuthenticationError("Agent credentials required for token requests")
            
        try:
            # Create DPoP proof for the token request
            token_endpoint = f"{self.registry_url}/tokens/create"
            # Normalize URL (this will ensure HTTPS for registry URLs)
            token_endpoint = normalize_url(token_endpoint)
            logger.debug(f"Creating DPoP proof for token request to: {token_endpoint}")
            
            dpop_proof = self._dpop.create_proof(
                "POST",
                token_endpoint,
                self._private_key
            )
            logger.debug("DPoP proof created successfully")
            
            logger.debug("Requesting token from registry...")
            # Convert target_agent_id to string before passing to get_token
            token = await self._token_manager.get_token(
                self._agent_id,
                self._agent_secret,
                str(target_agent_id) if isinstance(target_agent_id, UUID) else target_agent_id,
                dpop_proof,
                self._public_key,
                registry_url=token_endpoint.rsplit('/tokens/create', 1)[0]  # Pass the base URL with correct scheme
            )
            logger.debug(f"Token received successfully: {token[:20]}...")
            
            return token
            
        except Exception as e:
            logger.error(f"Error getting interaction token: {str(e)}", exc_info=True)
            if isinstance(e, (AuthenticationError, RegistryError)):
                raise
            raise RegistryError(
                status_code=500,
                detail=f"Failed to get interaction token: {str(e)}"
            )
        
    async def protect_request(
        self,
        method: str,
        url: str,
        target_agent_id: str | UUID,
        existing_headers: Optional[Dict[str, str]] = None
    ) -> Dict[str, str]:
        """Add protection headers to a request.
        
        Args:
            method: HTTP method of the request
            url: Target URL
            target_agent_id: ID of the target agent (can be string or UUID)
            existing_headers: Optional existing headers to include
            
        Returns:
            Dict[str, str]: Headers with protection added
            
        Raises:
            AuthenticationError: If credentials are missing or invalid
            RegistryError: If the registry service returns an error
        """
        logger = logging.getLogger(__name__)
        logger.debug(f"Protecting request - Method: {method}, URL: {url}")
        logger.debug(f"Target agent ID: {target_agent_id}")
        logger.debug(f"Existing headers: {existing_headers}")
        logger.debug(f"Using agent ID: {self._agent_id}")
        logger.debug(f"Registry URL: {self.registry_url}")
        
        if not self._private_key:
            logger.error("Missing private key")
            raise AuthenticationError("Private key required for protecting requests")
            
        try:
            # Start with existing headers
            headers = existing_headers.copy() if existing_headers else {}
            logger.debug(f"Initial headers: {headers}")
            
            # Convert target_agent_id to UUID if it's a string
            if isinstance(target_agent_id, str):
                target_agent_id = UUID(target_agent_id)
                logger.debug(f"Converted target_agent_id to UUID: {target_agent_id}")
            
            # Add DPoP proof
            logger.debug("Generating DPoP proof...")
            logger.debug(f"DPoP proof method: {method}")
            logger.debug(f"DPoP proof URL: {url}")
            logger.debug("Private key present for DPoP proof generation")
            
            # Generate DPoP proof for the actual request URL
            proof = self._dpop.create_proof(method, url, self._private_key)
            logger.debug(f"Generated DPoP proof: {proof[:50]}...")
            
            # Get token for target agent (always use HTTPS for registry)
            logger.debug(f"Getting interaction token for target agent: {target_agent_id}")
            token = await self.get_interaction_token(target_agent_id)
            logger.debug(f"Got interaction token: {token[:20]}...")
            
            # Add auth headers
            headers.update({
                "dpop": proof,
                "authorization": f"Bearer {token}",
                "target-agent-id": str(target_agent_id)
            })
            logger.debug(f"Final headers: {headers}")
            
            return headers
            
        except Exception as e:
            logger.error(f"Error protecting request: {str(e)}", exc_info=True)
            if isinstance(e, (AuthenticationError, RegistryError)):
                raise
            raise RegistryError(
                status_code=500,
                detail=f"Failed to protect request: {str(e)}"
            )
        
    async def verify_request(
        self,
        method: str,
        url: str,
        headers: Dict[str, str]
    ) -> bool:
        """Verify an incoming request.
        
        Args:
            method: HTTP method of the request
            url: URL of the request
            headers: Request headers
            
        Returns:
            bool: True if request is valid
            
        Raises:
            AuthenticationError: If verification fails
        """
        logger = logging.getLogger(__name__)
        logger.debug("Verifying request...")
        logger.debug(f"Method: {method}")
        logger.debug(f"URL: {url}")
        logger.debug(f"Headers: {headers}")
        
        # Extract token from Authorization header
        auth_header = headers.get("authorization")
        if not auth_header:
            logger.error("Missing authorization header")
            raise AuthenticationError("Missing authorization header")
            
        token = auth_header
        if token.startswith("Bearer "):
            token = token.replace("Bearer ", "")
            
        # Extract DPoP proof
        dpop = headers.get("dpop")
        if not dpop:
            logger.error("Missing DPoP proof header")
            raise AuthenticationError("Missing DPoP proof header")
            
        # Get target agent ID if present
        target_agent_id = headers.get("target-agent-id")
        logger.debug(f"Target agent ID: {target_agent_id}")
        
        try:
            # Call registry's verify endpoint
            logger.debug("Making request to registry verify endpoint...")
            
            # Configure client to enforce HTTPS for registry URLs
            transport = httpx.AsyncHTTPTransport(
                verify=True,
                retries=1
            )
            
            verify_url = f"{self.registry_url}/tokens/verify"
            
            # Create a new DPoP proof specifically for the verification request
            verification_proof = self._dpop.create_proof(
                "POST",  # Verification endpoint uses POST
                verify_url,
                self._private_key
            )
            
            async with httpx.AsyncClient(
                transport=transport,
                follow_redirects=False,
                base_url="https://api.getauthed.dev" if "getauthed.dev" in self.registry_url else self.registry_url
            ) as client:
                verify_headers = {
                    "authorization": f"Bearer {token}",
                    "dpop": verification_proof,  # Our new proof for this verification request
                    **({"target-agent-id": target_agent_id} if target_agent_id else {})
                }
                logger.debug(f"Verify request headers: {verify_headers}")
                
                response = await client.post(
                    "/tokens/verify",
                    headers=verify_headers
                )
                
                logger.debug(f"Verify response status: {response.status_code}")
                logger.debug(f"Verify response body: {response.text}")
                
                if response.status_code == 401:
                    raise AuthenticationError(response.text)
                elif response.status_code != 200:
                    raise RegistryError(
                        status_code=response.status_code,
                        detail=response.text
                    )
                    
                return True
                
        except AuthenticationError:
            raise
        except Exception as e:
            logger.error(f"Error verifying request: {str(e)}", exc_info=True)
            raise AuthenticationError(f"Failed to verify request: {str(e)}") 