"""Authentication handler for the CLI."""

import httpx
from typing import Dict
from urllib.parse import urljoin
from uuid import UUID
import click

class CLIAuth:
    """Handles authentication for provider operations via CLI."""
    
    def __init__(
        self,
        registry_url: str,
        provider_id: UUID,
        provider_secret: str
    ):
        """Initialize CLI auth handler.
        
        Args:
            registry_url: Base URL of the registry
            provider_id: The provider's ID
            provider_secret: The provider's secret for authentication
        """
        self.registry_url = registry_url.rstrip('/')
        self.provider_id = provider_id
        self._provider_secret = provider_secret
        
        if not provider_secret:
            raise ValueError("Provider secret is required")
    
    def get_headers(self) -> Dict[str, str]:
        """Get authentication headers for requests."""
        return {
            "provider-secret": self._provider_secret
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
        
        # Debug logging
        click.echo(f"Making request to: {url}", err=True)
        click.echo(f"Headers: {headers}", err=True)
        
        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                url,
                headers=headers,
                **kwargs
            )
            
            # Debug logging
            click.echo(f"Response status: {response.status_code}", err=True)
            click.echo(f"Response body: {response.text}", err=True)
            
            return response 