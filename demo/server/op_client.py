import os
from onepassword.client import Client
from typing import Dict, List, Optional, Any

class OnePasswordClient:
    """Wrapper around 1Password SDK to retrieve secrets."""
    
    def __init__(self):
        """Initialize the 1Password client using environment variables."""
        # These should be set in .env or provided securely
        self.op_token = os.getenv("OP_SERVICE_ACCOUNT_TOKEN")
        self.client = None
        
    async def connect(self):
        """Create connection to 1Password."""
        if not self.op_token:
            raise ValueError("OP_SERVICE_ACCOUNT_TOKEN environment variable is not set")
        
        # Initialize the 1Password client
        self.client = await Client.authenticate(
            auth=self.op_token, 
            integration_name="Authed MCP 1Password Integration", 
            integration_version="v1.0.0"
        )
        return self.client
    
    async def get_secret(self, vault_id_or_name: str, item_id_or_name: str, field_name: str = "credential") -> Any:
        """
        Retrieve a secret from 1Password.
        
        Args:
            vault_id_or_name (str): The ID or name of the vault
            item_id_or_name (str): The ID or title of the item
            field_name (str, optional): The field to retrieve, defaults to "credential"
            
        Returns:
            The secret value if field_name is specified, otherwise information about the item
        """
        if not self.client:
            await self.connect()
        
        # First, find the vault
        vault_info = await self._find_vault(vault_id_or_name)
        if not vault_info:
            raise ValueError(f"Vault '{vault_id_or_name}' not found")
        
        vault_id = vault_info["id"]
        vault_title = vault_info["name"]
        
        # Then, find the item
        item_info = await self._find_item(vault_id, item_id_or_name)
        if not item_info:
            raise ValueError(f"Item '{item_id_or_name}' not found in vault '{vault_title}'")
        
        item_id = item_info["id"]
        item_title = item_info["title"]
        
        # Use the secret reference directly
        try:
            # Format: op://<vault>/<item>/<field>
            # Use vault title and item title in the reference
            secret_ref = f"op://{vault_title}/{item_title}/{field_name}"
            return await self.client.secrets.resolve(secret_ref)
        except Exception as e:
            raise ValueError(f"Error retrieving secret: {e}")
    
    async def _find_vault(self, vault_id_or_name: str) -> Optional[Dict[str, str]]:
        """Find a vault by ID or name."""
        vaults = await self.list_vaults()
        
        # First try exact ID match
        for vault in vaults:
            if vault["id"] == vault_id_or_name:
                return vault
        
        # Then try exact name match
        for vault in vaults:
            if vault["name"] == vault_id_or_name:
                return vault
                
        # Finally try case-insensitive name match
        for vault in vaults:
            if vault["name"].lower() == vault_id_or_name.lower():
                return vault
                
        return None
    
    async def _find_item(self, vault_id: str, item_id_or_name: str) -> Optional[Dict[str, str]]:
        """Find an item by ID or name in a specific vault."""
        items = await self.list_items(vault_id)
        
        # First try exact ID match
        for item in items:
            if item["id"] == item_id_or_name:
                return item
        
        # Then try exact title match
        for item in items:
            if item["title"] == item_id_or_name:
                return item
                
        # Finally try case-insensitive title match
        for item in items:
            if item["title"].lower() == item_id_or_name.lower():
                return item
                
        return None
    
    async def list_vaults(self) -> List[Dict[str, str]]:
        """List all available vaults."""
        if not self.client:
            await self.connect()
        
        result = []
        vaults = await self.client.vaults.list_all()
        async for vault in vaults:
            result.append({"id": vault.id, "name": vault.title})
        return result
    
    async def list_items(self, vault_id_or_name: str) -> List[Dict[str, str]]:
        """List all items in a vault."""
        if not self.client:
            await self.connect()
        
        # Find the vault first if a name is provided
        if not vault_id_or_name.startswith("op") and not vault_id_or_name.isalnum():
            vault_info = await self._find_vault(vault_id_or_name)
            if not vault_info:
                raise ValueError(f"Vault '{vault_id_or_name}' not found")
            vault_id = vault_info["id"]
        else:
            vault_id = vault_id_or_name
        
        result = []
        items = await self.client.items.list_all(vault_id)
        async for item in items:
            result.append({"id": item.id, "title": item.title})
        return result
