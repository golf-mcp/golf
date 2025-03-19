"""Authentication handler for CLI commands."""

import httpx
from typing import Dict
from urllib.parse import urljoin
from uuid import UUID

class CLIAuth:
    """Handles authentication for CLI commands."""
    
    def __init__(
        self,
        registry_url: str,
        provider_id: UUID,
        provider_secret: str,
        debug: bool = False,
    ):
        """Initialize CLI auth handler.
        
        Args:
            registry_url: Base URL of the registry
            provider_id: The provider's ID
            provider_secret: The provider's secret for authentication
            debug: Whether to enable debug output
        """
        self.registry_url = registry_url.rstrip('/')
        self.provider_id = provider_id
        self.provider_secret = provider_secret
        self.debug = debug
        
        if not provider_secret:
            raise ValueError("Provider secret is required")
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests."""
        return {
            "provider-secret": self.provider_secret
        }
    
    async def request(
        self,
        method: str,
        path: str,
        **kwargs
    ) -> httpx.Response:
        """Make an authenticated request to the registry.
        
        Args:
            method: HTTP method
            path: API path (will be joined with registry URL)
            **kwargs: Additional arguments to pass to httpx
            
        Returns:
            httpx.Response: The response from the registry
            
        Raises:
            httpx.RequestError: If the request fails
        """
        url = urljoin(self.registry_url, path)
        
        # Add auth headers
        headers = kwargs.pop('headers', {})
        headers.update(self.get_headers())
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            
            return response 

    @property
    def list_agents_url(self) -> str:
        """Get URL for listing agents."""
        return f"{self.registry_url}/providers/list-agents/{self.provider_id}"

    def list_agents(self) -> httpx.Response:
        """List all agents for the provider."""
        response = httpx.get(
            self.list_agents_url,
            headers=self.get_headers()
        )
        
        return response 