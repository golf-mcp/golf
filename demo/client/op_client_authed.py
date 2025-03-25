import os
import sys
import asyncio
import logging
import traceback
from typing import List, Dict, Any
from contextlib import AsyncExitStack
import json
from authed.sdk import Authed
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

# Import our new Authed-MCP client utilities
from integrations.mcp import get_auth_headers

load_dotenv()

# Load environment variables from .env file
dotenv_path = os.path.join(os.path.dirname(__file__), '..', 'server', '.env')
if os.path.exists(dotenv_path):
    load_dotenv(dotenv_path)
    print(f"Loaded environment variables from {dotenv_path}")
else:
    print(f"Warning: .env file not found at {dotenv_path}")

# Set up more detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
# Reduce noise from other libraries
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

class OnePasswordAuthedClient:
    """MCP client that connects to an Authed-protected 1Password service."""
    
    def __init__(self):
        """Initialize the client."""
        logger.info("Initializing OnePasswordAuthedClient")
        
        # Check required environment variables
        required_vars = ["AUTHED_REGISTRY_URL", "AUTHED_AGENT_ID", "AUTHED_AGENT_SECRET"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            # Initialize Authed SDK
            logger.info("Initializing Authed SDK...")
            self.authed = Authed.initialize(
                registry_url=os.getenv("AUTHED_REGISTRY_URL", "https://api.getauthed.dev"),
                agent_id=os.getenv("AUTHED_AGENT_ID"),
                agent_secret=os.getenv("AUTHED_AGENT_SECRET"),
                private_key=os.getenv("AUTHED_PRIVATE_KEY"),
                public_key=os.getenv("AUTHED_PUBLIC_KEY")
            )
            logger.info("Authed SDK initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Authed SDK: {str(e)}")
            raise
        
        # Server URL from environment variables
        self.server_url = os.getenv("OP_SERVICE_URL", "http://localhost:8000/sse")
        logger.info(f"Using service URL: {self.server_url}")
        
        # Initialize session and context variables
        self.session = None
        self.exit_stack = AsyncExitStack()
        self._streams_context = None
        self._session_context = None
        
        # Get target agent ID - this should be the agent ID of the server we're connecting to
        self.target_agent_id = os.getenv("TARGET_AGENT_ID")
        if not self.target_agent_id:
            logger.warning("TARGET_AGENT_ID not set - authentication may fail")
        
    async def connect(self):
        """Connect to the 1Password MCP service."""
        try:
            logger.info(f"Connecting to MCP server at {self.server_url}")
            
            # Get target agent ID - the ID of the server we're connecting to
            target_agent_id = self.target_agent_id
            self_agent_id = self.authed.agent_id
            
            # Check if target_agent_id is the same as self_agent_id (this won't work)
            if target_agent_id and target_agent_id == self_agent_id:
                logger.warning(f"Target agent ID ({target_agent_id}) is the same as this agent's ID - this will not work with Authed")
                target_agent_id = None
            
            # Use our new Authed-MCP package to create authentication headers
            headers = await get_auth_headers(
                authed=self.authed,
                url=self.server_url,
                method="GET",
                target_agent_id=target_agent_id,
                fallback=True,
                debug=True
            )
            
            logger.info(f"Created authentication headers: {list(headers.keys())}")
            
            # Create SSE client with the authentication headers
            try:
                logger.debug("Creating SSE client context")
                self._streams_context = sse_client(
                    url=self.server_url,
                    headers=headers,
                    timeout=30.0,   # Increase timeout for the connection
                    sse_read_timeout=120.0  # Increase read timeout
                )
                
                logger.debug("Entering streams context")
                # Enter the streams context
                streams = await self._streams_context.__aenter__()
                
                logger.debug("Creating session context")
                # Create session context
                self._session_context = ClientSession(*streams)
                
                logger.debug("Entering session context")
                # Enter the session context
                self.session = await self._session_context.__aenter__()
                
                logger.debug("Initializing session")
                # Initialize the session
                await self.session.initialize()
                
                logger.debug("Listing tools to verify connection")
                # List available tools to verify connection
                response = await self.session.list_tools()
                tools = response.tools
                logger.info(f"Connected to server with tools: {[tool.name for tool in tools]}")
                
                logger.info("Successfully connected to MCP server")
                return self.session
            except Exception as e:
                logger.error(f"Error connecting to MCP server: {str(e)}")
                logger.debug(f"Connection error details: {traceback.format_exc()}")
                raise
        except Exception as e:
            logger.error(f"Failed to connect: {str(e)}")
            raise
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        logger.info("Disconnecting from MCP server")
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
                self._session_context = None
                logger.debug("Closed session context")
            
            if self._streams_context:
                await self._streams_context.__aexit__(None, None, None)
                self._streams_context = None
                logger.debug("Closed streams context")
            
            self.session = None
            logger.info("Disconnected from MCP server")
        except Exception as e:
            logger.error(f"Error during disconnect: {str(e)}")
            logger.debug(f"Disconnect error details: {traceback.format_exc()}")
            raise
    
    async def list_vaults(self) -> List[Dict[str, str]]:
        """List all available 1Password vaults."""
        logger.info("Listing 1Password vaults")
        
        if not self.session:
            logger.info("Session not connected, connecting now")
            await self.connect()
        
        try:
            result = await self.session.call_tool("onepassword_list_vaults")
            logger.info("Successfully retrieved vaults response")
            
            # Parse the content from the response
            content = result.content
            
            # If content is a list with a single TextContent item
            if isinstance(content, list) and len(content) == 1 and hasattr(content[0], 'text'):
                # Extract the text which should be a JSON string
                json_str = content[0].text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Parse the JSON string into a Python object
                import json
                vaults = json.loads(json_str)
                
                # Make sure we got a list
                if not isinstance(vaults, list):
                    vaults = [vaults]
                    
                logger.info(f"Successfully parsed {len(vaults)} vaults")
                return vaults
            else:
                # Just return the content as-is if it's already a list
                logger.info(f"Content is already parsed: {type(content)}")
                return content
                
        except Exception as e:
            logger.error(f"Error listing vaults: {str(e)}")
            raise

    async def list_items(self, vault_id: str) -> List[Dict[str, str]]:
        """List all items in a vault."""
        logger.info(f"Listing items in vault {vault_id}")

        if not self.session:
            logger.info("Session not connected, connecting now")
            await self.connect()
            
        try:
            result = await self.session.call_tool("onepassword_list_items", {
                "vault_id": vault_id
            })
            logger.info(f"Successfully retrieved items response")
            
            # Parse the content from the response
            content = result.content
            
            # If content is a list with a single TextContent item
            if isinstance(content, list) and len(content) == 1 and hasattr(content[0], 'text'):
                # Extract the text which should be a JSON string
                json_str = content[0].text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Parse the JSON string into a Python object
                import json
                items = json.loads(json_str)
                
                # Make sure we got a list
                if not isinstance(items, list):
                    items = [items]
                    
                logger.info(f"Successfully parsed {len(items)} items")
                return items
            elif hasattr(content, 'text'):  # If content is a single TextContent
                json_str = content.text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Parse the JSON string
                import json
                items = json.loads(json_str)
                
                # Make sure we got a list
                if not isinstance(items, list):
                    items = [items]
                    
                logger.info(f"Successfully parsed {len(items)} items")
                return items
            else:
                # Just return the content as-is if it's already a list
                logger.info(f"Content is already parsed: {type(content)}")
                return content
                
        except Exception as e:
            logger.error(f"Error listing items in vault {vault_id}: {str(e)}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            raise

    async def get_secret(self, vault_id: str, item_id: str, field_name: str = "credential") -> Any:
        """Get a secret from 1Password."""
        logger.info(f"Getting secret from vault={vault_id}, item={item_id}, field={field_name}")
        
        if not self.session:
            logger.info("Session not connected, connecting now")
            await self.connect()
        
        try:
            result = await self.session.call_tool("onepassword_get_secret", {
                "vault_id": vault_id,
                "item_id": item_id,
                "field_name": field_name
            })
            logger.info("Successfully retrieved secret response")
            
            # Parse the content from the response
            content = result.content
            
            # If content is a list with a single TextContent item
            if isinstance(content, list) and len(content) == 1 and hasattr(content[0], 'text'):
                # Extract the text which should be a JSON string
                json_str = content[0].text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                return json.loads(json_str)
            elif hasattr(content, 'text'):  # If content is a single TextContent
                return content.text
            else:
                # Just return the content as-is
                return content
                
        except Exception as e:
            logger.error(f"Error getting secret: {str(e)}")
            logger.debug(f"Error details: {traceback.format_exc()}")
            raise

async def main():
    """Simple test function."""
    client = None
    try:
        logger.info("Starting 1Password Authed client demo")
        
        # Initialize client
        client = OnePasswordAuthedClient()
        
        # List vaults
        print("\n=== Listing Vaults ===")
        vaults = await client.list_vaults()
        print(f"Found {len(vaults)} vaults:")
        for vault in vaults:
            print(f"  - ID: {vault.get('id', 'unknown')}, Name: {vault.get('name', 'unnamed')}")
        
        # If we have vaults, list items in the first one
        if vaults:
            first_vault = vaults[0]
            vault_id = first_vault.get('id')
            vault_name = first_vault.get('name', 'unnamed')
            
            print(f"\n=== Listing Items in '{vault_name}' Vault ===")
            items = await client.list_items(vault_id)
            print(f"Found {len(items)} items:")
            for item in items:
                print(f"  - ID: {item.get('id', 'unknown')}, Title: {item.get('title', 'unnamed')}")
            
            # If we have items, get a secret from the first one
            if items:
                first_item = items[0]
                item_id = first_item.get('id')
                item_title = first_item.get('title', 'unnamed')
                
                print(f"\n=== Getting Secret from '{item_title}' ===")
                secret = await client.get_secret(vault_id, item_id, "credential")
                
                # Just print success, don't display the actual secret
                print(f"Successfully retrieved secret from '{item_title}'")
                print(f"Secret type: {type(secret)}")
                
        print("\n=== Demo Completed Successfully ===")
            
    except Exception as e:
        print(f"\nERROR: {str(e)}")
        logger.error(f"Demo failed: {str(e)}")
        logger.debug(f"Error details: {traceback.format_exc()}")
        sys.exit(1)
    finally:
        # Make sure to clean up
        if client and client.session:
            await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main()) 