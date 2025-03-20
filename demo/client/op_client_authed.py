import os
import sys
import asyncio
import logging
import base64
import traceback
from typing import List, Dict, Any, Optional
from contextlib import AsyncExitStack

from authed.sdk import Authed
from mcp import ClientSession
from mcp.client.sse import sse_client
from dotenv import load_dotenv
import httpx

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
            
            # Create authentication headers
            headers = {
                'User-Agent': 'OnePasswordAuthedClient/1.0'
            }
            
            if target_agent_id:
                logger.info(f"Creating Authed authentication for target: {target_agent_id}")
                
                try:
                    # Get auth handler from Authed SDK
                    auth_handler = self.authed.auth
                    
                    # Create authentication headers manually
                    # This is similar to what protect_request would do internally
                    auth_headers = await auth_handler.protect_request(
                        method="GET",
                        url=self.server_url,
                        target_agent_id=target_agent_id
                    )
                    
                    # Add the auth headers to our headers dict
                    if auth_headers:
                        headers.update(auth_headers)
                        logger.info(f"Added Authed authentication headers: {list(auth_headers.keys())}")
                        logger.debug(f"Auth headers details: {auth_headers}")
                    else:
                        logger.warning("No authentication headers returned by Authed SDK")
                except Exception as e:
                    logger.error(f"Error creating Authed authentication: {str(e)}")
                    logger.debug(f"Authentication error details: {traceback.format_exc()}")
                    # Fall back to basic auth
                    target_agent_id = None
            
            # If still no target_agent_id or Authed auth failed, use basic auth
            if not target_agent_id or 'authorization' not in headers:
                logger.warning("Using fallback Basic authentication")
                auth_credentials = f"{self.authed.agent_id}:{os.getenv('AUTHED_AGENT_SECRET', '')}"
                encoded_credentials = base64.b64encode(auth_credentials.encode()).decode('utf-8')
                headers['Authorization'] = f"Basic {encoded_credentials}"
            
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
                
                return self.session
            except Exception as conn_error:
                detailed_error = str(conn_error)
                if not detailed_error:
                    detailed_error = f"Empty error ({type(conn_error).__name__}). Check server logs."
                
                logger.error(f"Connection error: {detailed_error}")
                logger.debug(f"Connection error details: {traceback.format_exc()}")
                
                # Try to diagnose the issue
                logger.info("Attempting to diagnose connection issue...")
                try:
                    # Make a simple request to check basic connectivity
                    async with httpx.AsyncClient() as client:
                        health_url = self.server_url.replace("/sse", "/health")
                        logger.info(f"Checking health endpoint: {health_url}")
                        response = await client.get(health_url, timeout=5.0)
                        logger.info(f"Health check response: {response.status_code}")
                        if response.status_code == 200:
                            logger.info(f"Health check successful: {response.text}")
                        else:
                            logger.warning(f"Health check failed: {response.text}")
                except Exception as health_e:
                    logger.warning(f"Health check failed: {str(health_e)}")
                
                raise
                
        except Exception as e:
            error_msg = str(e)
            if not error_msg:
                error_msg = f"Empty error ({type(e).__name__}). Check server logs."
            logger.error(f"Failed to connect to MCP server: {error_msg}")
            logger.debug(f"Connection failure details: {traceback.format_exc()}")
            await self.cleanup()
            raise ValueError(f"Connection failed: {error_msg}")
    
    async def cleanup(self):
        """Properly clean up the session and streams."""
        logger.info("Cleaning up MCP client resources")
        try:
            if self._session_context:
                await self._session_context.__aexit__(None, None, None)
                self._session_context = None
                
            if self._streams_context:
                await self._streams_context.__aexit__(None, None, None)
                self._streams_context = None
                
            self.session = None
            logger.info("Cleanup completed successfully")
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
    
    async def list_vaults(self) -> List[Dict[str, str]]:
        """List all available 1Password vaults."""
        logger.info("Listing 1Password vaults")
        if not self.session:
            logger.info("Session not connected, connecting now")
            await self.connect()
            
        try:
            result = await self.session.call_tool("onepassword_list_vaults", {})
            logger.info(f"Successfully retrieved vaults response")
            
            # Parse the content from the response
            # The content may be a list of TextContent objects with JSON strings
            content = result.content
            
            # If content is a list with a single TextContent item
            if isinstance(content, list) and len(content) == 1 and hasattr(content[0], 'text'):
                # Extract the text which should be a JSON string
                json_str = content[0].text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Parse the JSON string into a Python object
                import json
                vaults = json.loads(json_str)
                
                # Make sure we got a list (if it's a single item, wrap it)
                if not isinstance(vaults, list):
                    vaults = [vaults]
                    
                logger.info(f"Successfully parsed {len(vaults)} vaults")
                return vaults
            elif hasattr(content, 'text'):  # If content is a single TextContent
                json_str = content.text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Parse the JSON string
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
            logger.debug(f"Error details: {traceback.format_exc()}")
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
            
    async def get_secret(self, vault_id: str, item_id: str, field_name: Optional[str] = None) -> Any:
        """Get a secret from 1Password."""
        logger.info(f"Getting secret from vault={vault_id}, item={item_id}, field={field_name}")
        if not self.session:
            logger.info("Session not connected, connecting now")
            await self.connect()
            
        try:
            # Prepare arguments
            args = {
                "vault_id": vault_id,
                "item_id": item_id
            }
            
            # Add field_name if provided
            if field_name:
                args["field_name"] = field_name
                
            # Call the tool
            result = await self.session.call_tool("onepassword_get_secret", args)
            logger.info(f"Successfully retrieved secret response")
            
            # Parse the content from the response
            content = result.content
            
            # If content is a list with a single TextContent item
            if isinstance(content, list) and len(content) == 1 and hasattr(content[0], 'text'):
                # Extract the text which should be a JSON string
                json_str = content[0].text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Parse the JSON string into a Python object
                import json
                try:
                    secret = json.loads(json_str)
                    logger.info("Successfully parsed secret JSON")
                    return secret
                except json.JSONDecodeError:
                    # If not valid JSON, return the raw text
                    logger.info("Secret is not JSON, returning raw text")
                    return json_str
            elif hasattr(content, 'text'):  # If content is a single TextContent
                json_str = content.text
                logger.debug(f"Parsing JSON from TextContent: {json_str}")
                
                # Try to parse as JSON
                import json
                try:
                    secret = json.loads(json_str)
                    logger.info("Successfully parsed secret JSON")
                    return secret
                except json.JSONDecodeError:
                    # If not valid JSON, return the raw text
                    logger.info("Secret is not JSON, returning raw text")
                    return json_str
            else:
                # Just return the content as-is
                logger.info(f"Content is already parsed: {type(content)}")
                return content
                
        except Exception as e:
            logger.error(f"Error getting secret from vault={vault_id}, item={item_id}: {str(e)}")
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
            await client.cleanup()

if __name__ == "__main__":
    asyncio.run(main()) 